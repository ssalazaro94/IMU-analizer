import { createClient } from "@/lib/supabase/server";
import { getCurrentUser } from "@/lib/supabase/profile";
import type { AnalysisResultRow, FileRow } from "@/lib/types";
import { UploadDashboard } from "./upload-dashboard";

export default async function Home() {
  const user = await getCurrentUser();
  const supabase = await createClient();

  const { data: files } = await supabase
    .from("files")
    .select("*")
    .order("created_at", { ascending: false })
    .returns<FileRow[]>();

  const { data: results } = await supabase
    .from("analysis_results")
    .select("*")
    .order("created_at", { ascending: false })
    .returns<AnalysisResultRow[]>();

  // Nos quedamos solo con el resultado más reciente por archivo.
  const latestResultByFileId: Record<string, AnalysisResultRow> = {};
  for (const result of results ?? []) {
    if (!latestResultByFileId[result.file_id]) {
      latestResultByFileId[result.file_id] = result;
    }
  }

  return (
    <UploadDashboard
      user={user!}
      initialFiles={files ?? []}
      initialResults={latestResultByFileId}
    />
  );
}
