-- Permite borrar archivos a cualquier rol (antes solo `root` podía). El
-- alcance sigue el mismo criterio que la visibilidad: el uploader puede
-- borrar lo suyo, `root` puede borrar cualquier cosa. `analysis_results` no
-- necesita policy de delete propia porque cae por `on delete cascade` desde
-- `files`. Escrito de forma idempotente igual que las migraciones anteriores.

drop policy if exists "files_delete_root_only" on public.files;
drop policy if exists "files_delete_own_or_root" on public.files;
create policy "files_delete_own_or_root"
  on public.files for delete
  to authenticated
  using (uploaded_by = auth.uid() or public.is_root());

drop policy if exists "csv_uploads_delete_root_only" on storage.objects;
drop policy if exists "csv_uploads_delete_own_or_root" on storage.objects;
create policy "csv_uploads_delete_own_or_root"
  on storage.objects for delete
  to authenticated
  using (
    bucket_id = 'csv-uploads'
    and (
      public.is_root()
      or (storage.foldername(name))[1] = auth.uid()::text
    )
  );
