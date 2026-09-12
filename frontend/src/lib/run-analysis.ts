import "server-only";

import type { SupabaseClient } from "@supabase/supabase-js";
import type { AnalysisServiceResponse, EquationSettings, Pierna } from "@/lib/types";

const ANALYSIS_SERVICE_URL = process.env.NEXT_PUBLIC_ANALYSIS_SERVICE_URL!;

const MENSAJE_COLD_START =
  "No se pudo conectar con el servicio de análisis. Si estuvo inactivo puede tardar " +
  "hasta un minuto en reactivarse — probá 'Volver a analizar' en un momento.";

/**
 * Llama al microservicio y persiste el resultado (o el error) en Supabase.
 * Pensado para correr dentro de `after()`, desacoplado de la respuesta al cliente,
 * porque el cold start de Render puede tardar ~30-50s.
 */
export async function runAnalysisAndPersist(params: {
  supabase: SupabaseClient;
  fileId: string;
  userId: string;
  csvBlob: Blob;
  csvFilename: string;
  pierna: Pierna;
  settings: EquationSettings;
}) {
  const { supabase, fileId, userId, csvBlob, csvFilename, pierna, settings } = params;

  await supabase.from("files").update({ status: "processing" }).eq("id", fileId);

  try {
    const form = new FormData();
    form.set("file", csvBlob, csvFilename);
    form.set("pierna", pierna);
    form.set("alpha", String(settings.alpha));
    form.set("umbral_balanceo_deg_s", String(settings.umbral_balanceo_deg_s));
    form.set("umbral_tc_deg_s", String(settings.umbral_tc_deg_s));
    form.set("distancia_min_balanceo_s", String(settings.distancia_min_balanceo_s));
    form.set("distancia_min_minimos_s", String(settings.distancia_min_minimos_s));

    let response: Response;
    try {
      response = await fetch(`${ANALYSIS_SERVICE_URL}/analyze`, { method: "POST", body: form });
    } catch {
      throw new Error(MENSAJE_COLD_START);
    }

    if (!response.ok) {
      // 502/503/504 son típicos del proxy de Render mientras el contenedor
      // todavía está despertando de un cold start (no llega a responder JSON).
      if ([502, 503, 504].includes(response.status)) {
        throw new Error(MENSAJE_COLD_START);
      }

      let detalle: string | null = null;
      try {
        const cuerpo = await response.json();
        if (typeof cuerpo?.detail === "string") detalle = cuerpo.detail;
      } catch {
        // la respuesta de error no era JSON, seguimos con el mensaje genérico
      }
      throw new Error(detalle ?? `El servicio de análisis respondió con un error (${response.status}).`);
    }

    const result: AnalysisServiceResponse = await response.json();

    const { error: insertError } = await supabase.from("analysis_results").insert({
      file_id: fileId,
      parametros_usados: result.parametros,
      deteccion_lado: result.deteccion_lado,
      frecuencia_muestreo_hz: result.frecuencia_muestreo_hz,
      duracion_ciclo_promedio_s: result.metricas.duracion_promedio_ciclo_s,
      tiempo_apoyo_promedio_s: result.metricas.tiempo_promedio_apoyo_s,
      tiempo_balanceo_promedio_s: result.metricas.tiempo_promedio_balanceo_s,
      cadencia_promedio_pasos_min: result.metricas.cadencia_promedio_pasos_min,
      raw_json: result,
      created_by: userId,
    });

    if (insertError) throw insertError;

    await supabase
      .from("files")
      .update({ status: "done", error_message: null })
      .eq("id", fileId);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Error desconocido al analizar el CSV.";
    await supabase.from("files").update({ status: "error", error_message: message }).eq("id", fileId);
  }
}
