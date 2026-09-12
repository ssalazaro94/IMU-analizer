-- Restringe la visibilidad de archivos y resultados por rol: `root` sigue
-- viendo todo (workspace compartido para el rol de más confianza), pero
-- `admin` ahora solo ve los archivos que él mismo subió (antes cualquier
-- admin/root veía todo, sin aislamiento por uploader). Escrito de forma
-- idempotente igual que la migración inicial.

-- ---------------------------------------------------------------------------
-- files: solo el uploader o un root pueden ver la fila.
-- ---------------------------------------------------------------------------

drop policy if exists "files_select_authenticated" on public.files;
drop policy if exists "files_select_own_or_root" on public.files;
create policy "files_select_own_or_root"
  on public.files for select
  to authenticated
  using (uploaded_by = auth.uid() or public.is_root());

-- ---------------------------------------------------------------------------
-- analysis_results: se hereda la visibilidad del archivo asociado (no de
-- `created_by`, porque quien re-analiza no es necesariamente el uploader).
-- ---------------------------------------------------------------------------

drop policy if exists "analysis_results_select_authenticated" on public.analysis_results;
drop policy if exists "analysis_results_select_own_or_root" on public.analysis_results;
create policy "analysis_results_select_own_or_root"
  on public.analysis_results for select
  to authenticated
  using (
    public.is_root()
    or exists (
      select 1 from public.files f
      where f.id = analysis_results.file_id
        and f.uploaded_by = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Storage (csv-uploads): mismo criterio, usando la carpeta `<user_id>/...`
-- en la que ya se guarda cada CSV.
-- ---------------------------------------------------------------------------

drop policy if exists "csv_uploads_select_authenticated" on storage.objects;
drop policy if exists "csv_uploads_select_own_or_root" on storage.objects;
create policy "csv_uploads_select_own_or_root"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'csv-uploads'
    and (
      public.is_root()
      or (storage.foldername(name))[1] = auth.uid()::text
    )
  );
