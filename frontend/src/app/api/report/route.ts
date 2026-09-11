import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { AnalysisResultRow, FileRow } from "@/lib/types";

export const maxDuration = 30;

const ANALYSIS_SERVICE_URL = process.env.NEXT_PUBLIC_ANALYSIS_SERVICE_URL!;

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

  const { data: fileRow } = await supabase
    .from("files")
    .select("*")
    .eq("id", fileId)
    .single<FileRow>();

  if (!fileRow) {
    return NextResponse.json({ error: "Archivo no encontrado." }, { status: 404 });
  }

  const { data: result } = await supabase
    .from("analysis_results")
    .select("*")
    .eq("file_id", fileId)
    .order("created_at", { ascending: false })
    .limit(1)
    .single<AnalysisResultRow>();

  if (!result) {
    return NextResponse.json({ error: "Este archivo todavía no tiene resultados." }, { status: 404 });
  }

  const response = await fetch(`${ANALYSIS_SERVICE_URL}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resultado: result.raw_json,
      nombre_archivo: fileRow.nombre_original,
    }),
  });

  if (!response.ok) {
    return NextResponse.json({ error: "No se pudo generar el PDF." }, { status: 502 });
  }

  const pdfBytes = await response.arrayBuffer();
  const nombreDescarga = fileRow.nombre_original.replace(/\.csv$/i, "") + "_reporte.pdf";

  return new NextResponse(pdfBytes, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${nombreDescarga}"`,
    },
  });
}
