import { after } from "next/server";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { runAnalysisAndPersist } from "@/lib/run-analysis";
import type { EquationSettings } from "@/lib/types";

export const maxDuration = 60;

// Vercel limita el body de las Serverless Functions (runtime Node.js) a ~4.5MB
// a nivel de plataforma, sin importar lo que se configure acá — dejamos margen
// para el resto del multipart (boundary, otros campos del form).
const MAX_CSV_BYTES = 4 * 1024 * 1024; // 4MB

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

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Falta el archivo CSV." }, { status: 422 });
  }
  if (file.size === 0 || file.size > MAX_CSV_BYTES) {
    return NextResponse.json({ error: "El archivo está vacío o supera 4MB." }, { status: 422 });
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
    // "pierna" ya no se le pide al usuario (ver [[pierna_derecha_izquierda]] en
    // memoria: declararla no cambia el resultado del análisis desde que el
    // ajuste automático de sentido corre siempre). Se guarda un valor fijo
    // solo para satisfacer la columna NOT NULL; la pierna que se muestra en la
    // UI se deriva de `deteccion_lado` una vez que el análisis termina.
    .insert({
      uploaded_by: user.id,
      nombre_original: file.name,
      storage_path: storagePath,
      pierna: "derecha",
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
      settings,
    }),
  );

  return NextResponse.json({ file_id: fileRow.id }, { status: 202 });
}
