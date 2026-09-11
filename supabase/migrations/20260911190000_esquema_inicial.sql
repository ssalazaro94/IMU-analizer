-- Esquema inicial: roles (root/admin), parámetros globales del algoritmo,
-- archivos subidos y resultados de análisis. Escrito de forma idempotente
-- porque se aplicó una vez vía `supabase db query --linked` (Management API,
-- sin contraseña directa de Postgres) y podría volver a aplicarse más
-- adelante con `supabase db push` si se configura la contraseña de la DB.

-- ---------------------------------------------------------------------------
-- Perfiles y roles
-- ---------------------------------------------------------------------------

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  role text not null default 'admin' check (role in ('root', 'admin')),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Función helper (security definer) para chequear el rol sin recursión de RLS.
create or replace function public.is_root()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles where id = auth.uid() and role = 'root'
  );
$$;

-- Crea el perfil automáticamente cuando se crea un usuario nuevo en Supabase Auth.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role) values (new.id, 'admin')
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

drop policy if exists "profiles_select_authenticated" on public.profiles;
create policy "profiles_select_authenticated"
  on public.profiles for select
  to authenticated
  using (true);

drop policy if exists "profiles_update_root_only" on public.profiles;
create policy "profiles_update_root_only"
  on public.profiles for update
  to authenticated
  using (public.is_root())
  with check (public.is_root());

-- ---------------------------------------------------------------------------
-- Parámetros globales del algoritmo (fila única, id = 1)
-- ---------------------------------------------------------------------------

create table if not exists public.equation_settings (
  id smallint primary key default 1,
  alpha double precision not null default 0.995,
  umbral_balanceo_deg_s double precision not null default 50,
  umbral_tc_deg_s double precision not null default -20,
  distancia_min_balanceo_s double precision not null default 0.5,
  distancia_min_minimos_s double precision not null default 0.3,
  metodo_deteccion_lado text not null default 'pierna' check (metodo_deteccion_lado in ('pierna', 'auto')),
  updated_at timestamptz not null default now(),
  updated_by uuid references auth.users (id),
  constraint equation_settings_singleton check (id = 1)
);

insert into public.equation_settings (id)
values (1)
on conflict (id) do nothing;

alter table public.equation_settings enable row level security;

drop policy if exists "equation_settings_select_authenticated" on public.equation_settings;
create policy "equation_settings_select_authenticated"
  on public.equation_settings for select
  to authenticated
  using (true);

drop policy if exists "equation_settings_update_root_only" on public.equation_settings;
create policy "equation_settings_update_root_only"
  on public.equation_settings for update
  to authenticated
  using (public.is_root())
  with check (public.is_root());

-- ---------------------------------------------------------------------------
-- Archivos subidos
-- ---------------------------------------------------------------------------

create table if not exists public.files (
  id uuid primary key default gen_random_uuid(),
  uploaded_by uuid not null references auth.users (id),
  nombre_original text not null,
  storage_path text not null,
  pierna text not null check (pierna in ('derecha', 'izquierda')),
  status text not null default 'pending' check (status in ('pending', 'processing', 'done', 'error')),
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists files_created_at_idx on public.files (created_at desc);

alter table public.files enable row level security;

-- Workspace clínico compartido: cualquier admin/root ve todos los archivos
-- (no hay aislamiento por paciente/uploader). Revisar si esto cambia.
drop policy if exists "files_select_authenticated" on public.files;
create policy "files_select_authenticated"
  on public.files for select
  to authenticated
  using (true);

drop policy if exists "files_insert_own" on public.files;
create policy "files_insert_own"
  on public.files for insert
  to authenticated
  with check (uploaded_by = auth.uid());

drop policy if exists "files_update_uploader_or_root" on public.files;
create policy "files_update_uploader_or_root"
  on public.files for update
  to authenticated
  using (uploaded_by = auth.uid() or public.is_root())
  with check (uploaded_by = auth.uid() or public.is_root());

drop policy if exists "files_delete_root_only" on public.files;
create policy "files_delete_root_only"
  on public.files for delete
  to authenticated
  using (public.is_root());

-- ---------------------------------------------------------------------------
-- Resultados de análisis (una fila por corrida; "re-analizar" inserta una
-- fila nueva en vez de pisar la anterior, para mantener historial/auditoría)
-- ---------------------------------------------------------------------------

create table if not exists public.analysis_results (
  id uuid primary key default gen_random_uuid(),
  file_id uuid not null references public.files (id) on delete cascade,
  parametros_usados jsonb not null,
  deteccion_lado jsonb not null,
  frecuencia_muestreo_hz double precision,
  duracion_ciclo_promedio_s double precision,
  tiempo_apoyo_promedio_s double precision,
  tiempo_balanceo_promedio_s double precision,
  cadencia_promedio_pasos_min double precision,
  raw_json jsonb not null,
  created_at timestamptz not null default now(),
  created_by uuid not null references auth.users (id)
);

create index if not exists analysis_results_file_id_created_at_idx
  on public.analysis_results (file_id, created_at desc);

alter table public.analysis_results enable row level security;

drop policy if exists "analysis_results_select_authenticated" on public.analysis_results;
create policy "analysis_results_select_authenticated"
  on public.analysis_results for select
  to authenticated
  using (true);

drop policy if exists "analysis_results_insert_own" on public.analysis_results;
create policy "analysis_results_insert_own"
  on public.analysis_results for insert
  to authenticated
  with check (created_by = auth.uid());

drop policy if exists "analysis_results_delete_root_only" on public.analysis_results;
create policy "analysis_results_delete_root_only"
  on public.analysis_results for delete
  to authenticated
  using (public.is_root());

-- ---------------------------------------------------------------------------
-- Realtime (para que el frontend escuche cambios de estado sin polling)
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'files'
  ) then
    alter publication supabase_realtime add table public.files;
  end if;

  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'analysis_results'
  ) then
    alter publication supabase_realtime add table public.analysis_results;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Storage: bucket privado para los CSV originales
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('csv-uploads', 'csv-uploads', false)
on conflict (id) do nothing;

drop policy if exists "csv_uploads_insert_own" on storage.objects;
create policy "csv_uploads_insert_own"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'csv-uploads'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "csv_uploads_select_authenticated" on storage.objects;
create policy "csv_uploads_select_authenticated"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'csv-uploads');

drop policy if exists "csv_uploads_delete_root_only" on storage.objects;
create policy "csv_uploads_delete_root_only"
  on storage.objects for delete
  to authenticated
  using (bucket_id = 'csv-uploads' and public.is_root());
