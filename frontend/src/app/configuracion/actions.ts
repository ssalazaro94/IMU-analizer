"use server";

import { createClient } from "@/lib/supabase/server";

export type ConstanteState = { error: string | null; success: boolean; valor?: number };

const VALIDACIONES: Record<string, (v: number) => string | null> = {
  alpha: (v) => (v > 0 && v < 1 ? null : "Alpha debe estar entre 0 y 1 (sin incluirlos)."),
  umbral_balanceo_deg_s: (v) => (v > 0 ? null : "Debe ser mayor a 0."),
  umbral_tc_deg_s: (v) => (v < 0 ? null : "Debe ser negativo."),
  distancia_min_balanceo_s: (v) => (v > 0 ? null : "Debe ser mayor a 0."),
  distancia_min_minimos_s: (v) => (v > 0 ? null : "Debe ser mayor a 0."),
};

export async function actualizarConstante(
  _prevState: ConstanteState,
  formData: FormData,
): Promise<ConstanteState> {
  const campo = String(formData.get("campo"));
  const valor = Number(formData.get("valor"));

  const validar = VALIDACIONES[campo];
  if (!validar) {
    return { error: "Constante desconocida.", success: false };
  }
  if (!Number.isFinite(valor)) {
    return { error: "El valor debe ser un número válido.", success: false };
  }
  const errorValidacion = validar(valor);
  if (errorValidacion) {
    return { error: errorValidacion, success: false };
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return { error: "No autenticado.", success: false };
  }

  const { error } = await supabase
    .from("equation_settings")
    .update({ [campo]: valor, updated_at: new Date().toISOString(), updated_by: user.id })
    .eq("id", 1);

  if (error) {
    return { error: "No se pudo guardar (¿tenés permiso de root?).", success: false };
  }

  return { error: null, success: true, valor };
}
