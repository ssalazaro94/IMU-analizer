import { after } from "next/server";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { runAnalysisAndPersist } from "@/lib/run-analysis";
import type { EquationSettings, Pierna } from "@/lib/types";

export const maxDuration = 60;

const MAX_CSV_BYTES = 20 * 1024 * 1024; // 20MB

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "No autenticado." }, { status: 401 });
  }

  const form = await request.formData();
  const file = form.get("file");
  const pierna = form.get("pierna");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Falta el archivo CSV." }, { status: 422 });
  }
  if (pierna !== "derecha" && pierna !== "izquierda") {
    return NextResponse.json({ error: "Pierna inválida." }, { status: 422 });
  }
  if (file.size === 0 || file.size > MAX_CSV_BYTES) {
    return NextResponse.json({ error: "El archivo está vacío o supera 20MB." }, { status: 422 });
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

  const storagePath = `${user.id}/${crypto.randomUUID()}.csv`;
  const csvBlob = new Blob([await file.arrayBuffer()], { type: "text/csv" });

  const { error: uploadError } = await supabase.storage
    .from("csv-uploads")
    .upload(storagePath, csvBlob, { contentType: "text/csv" });

  if (uploadError) {
    return NextResponse.json({ error: "No se pudo guardar el CSV." }, { status: 500 });
  }

  const { data: fileRow, error: insertError } = await supabase
    .from("files")
    .insert({
      uploaded_by: user.id,
      nombre_original: file.name,
      storage_path: storagePath,
      pierna: pierna as Pierna,
    })
    .select("id")
    .single<{ id: string }>();

  if (insertError || !fileRow) {
    return NextResponse.json({ error: "No se pudo registrar el archivo." }, { status: 500 });
  }

  after(() =>
    runAnalysisAndPersist({
      supabase,
      fileId: fileRow.id,
      userId: user.id,
      csvBlob,
      csvFilename: file.name,
      pierna: pierna as Pierna,
      settings,
    }),
  );

  return NextResponse.json({ file_id: fileRow.id }, { status: 202 });
}
