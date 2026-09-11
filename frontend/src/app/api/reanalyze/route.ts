import { after, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { runAnalysisAndPersist } from "@/lib/run-analysis";
import type { EquationSettings, FileRow } from "@/lib/types";

export const maxDuration = 60;

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "No autenticado." }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  const fileId = body?.file_id;
  if (typeof fileId !== "string") {
    return NextResponse.json({ error: "Falta file_id." }, { status: 422 });
  }

  const { data: fileRow, error: fileError } = await supabase
    .from("files")
    .select("*")
    .eq("id", fileId)
    .single<FileRow>();

  if (fileError || !fileRow) {
    return NextResponse.json({ error: "Archivo no encontrado." }, { status: 404 });
  }

  const { data: settings, error: settingsError } = await supabase
    .from("equation_settings")
    .select("*")
    .eq("id", 1)
    .single<EquationSettings>();

  if (settingsError || !settings) {
    return NextResponse.json(
      { error: "No se pudieron leer los parámetros del algoritmo." },
      { status: 500 },
    );
  }

  const { data: csvFile, error: downloadError } = await supabase.storage
    .from("csv-uploads")
    .download(fileRow.storage_path);

  if (downloadError || !csvFile) {
    return NextResponse.json({ error: "No se pudo leer el CSV original." }, { status: 500 });
  }

  await supabase.from("files").update({ status: "pending", error_message: null }).eq("id", fileId);

  after(() =>
    runAnalysisAndPersist({
      supabase,
      fileId,
      userId: user.id,
      csvBlob: csvFile,
      csvFilename: fileRow.nombre_original,
      pierna: fileRow.pierna,
      settings,
    }),
  );

  return NextResponse.json({ file_id: fileId }, { status: 202 });
}
