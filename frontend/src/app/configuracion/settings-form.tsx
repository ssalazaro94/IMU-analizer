"use client";

import { useActionState, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { actualizarConstante, type ConstanteState } from "./actions";
import type { EquationSettings } from "@/lib/types";

const initialState: ConstanteState = { error: null, success: false };

export function SettingsForm({ initialSettings }: { initialSettings: EquationSettings }) {
  return (
    <div className="space-y-4">
      <EquationCard
        titulo="Filtro pasa-altas"
        formula="y[i] = x[i] − x[i−1] + α · y[i−1]"
        descripcion="Suaviza la señal del giroscopio y remueve la deriva/offset lento antes de detectar eventos de marcha."
      >
        <Constante
          etiqueta="α (alpha)"
          campo="alpha"
          valorInicial={initialSettings.alpha}
          step="0.001"
          ayuda="Entre 0 y 1. Más cerca de 1 = más agresivo quitando el offset. Default: 0.995."
        />
      </EquationCard>

      <EquationCard
        titulo="Detección de balanceo (mid-swing)"
        formula="balanceo detectado si señal(t) > umbral, separado del anterior por al menos la distancia mínima"
        descripcion="Marca el momento medio del balanceo del pie sobre la señal ya filtrada."
      >
        <Constante
          etiqueta="Umbral de balanceo"
          campo="umbral_balanceo_deg_s"
          valorInicial={initialSettings.umbral_balanceo_deg_s}
          step="0.1"
          unidad="deg/s"
          ayuda="Mayor a 0. Default: 50."
        />
        <Constante
          etiqueta="Distancia mínima entre balanceos"
          campo="distancia_min_balanceo_s"
          valorInicial={initialSettings.distancia_min_balanceo_s}
          step="0.01"
          unidad="s"
          ayuda="Mayor a 0. Default: 0.5."
        />
      </EquationCard>

      <EquationCard
        titulo="Mínimos locales (candidatos a IC/TC)"
        formula="mínimos locales de la señal filtrada, separados entre sí por al menos la distancia mínima"
        descripcion="Encuentra los puntos candidatos a contacto inicial (IC) y contacto terminal (TC)."
      >
        <Constante
          etiqueta="Distancia mínima entre mínimos"
          campo="distancia_min_minimos_s"
          valorInicial={initialSettings.distancia_min_minimos_s}
          step="0.01"
          unidad="s"
          ayuda="Mayor a 0. Default: 0.3."
        />
      </EquationCard>

      <EquationCard
        titulo="Contacto terminal (TC)"
        formula="TC válido si señal(TC) < umbral"
        descripcion="El mínimo local justo antes del balanceo se confirma como contacto terminal solo si su valor es lo bastante negativo."
      >
        <Constante
          etiqueta="Umbral de contacto terminal"
          campo="umbral_tc_deg_s"
          valorInicial={initialSettings.umbral_tc_deg_s}
          step="0.1"
          unidad="deg/s"
          ayuda="Menor a 0. Default: -20."
        />
      </EquationCard>
    </div>
  );
}

function EquationCard({
  titulo,
  formula,
  descripcion,
  children,
}: {
  titulo: string;
  formula: string;
  descripcion: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-6">
      <h2 className="text-sm font-semibold text-neutral-900">{titulo}</h2>
      <p className="mt-1 text-sm text-neutral-600">{descripcion}</p>
      <p className="mt-3 rounded-md bg-neutral-50 px-3 py-2 font-mono text-xs text-neutral-700">
        {formula}
      </p>
      <div className="mt-4 space-y-3 border-t border-neutral-100 pt-4">{children}</div>
    </div>
  );
}

function Constante({
  etiqueta,
  campo,
  valorInicial,
  step,
  unidad,
  ayuda,
}: {
  etiqueta: string;
  campo: string;
  valorInicial: number;
  step: string;
  unidad?: string;
  ayuda: string;
}) {
  const [editando, setEditando] = useState(false);
  const [valorMostrado, setValorMostrado] = useState(valorInicial);
  const [state, formAction, pending] = useActionState(actualizarConstante, initialState);

  useEffect(() => {
    if (state.success && state.valor !== undefined) {
      setValorMostrado(state.valor);
      setEditando(false);
    }
  }, [state]);

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-neutral-900">{etiqueta}</p>
          {!editando && (
            <p className="text-sm text-neutral-600">
              {valorMostrado}
              {unidad ? ` ${unidad}` : ""}
            </p>
          )}
        </div>
        {!editando && (
          <button
            type="button"
            onClick={() => setEditando(true)}
            className="shrink-0 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-medium text-neutral-700 transition hover:bg-neutral-50"
          >
            Editar constante
          </button>
        )}
      </div>

      {editando && (
        <form action={formAction} className="mt-2 flex items-start gap-2">
          <input type="hidden" name="campo" value={campo} />
          <div className="flex-1">
            <input
              type="number"
              name="valor"
              step={step}
              defaultValue={valorMostrado}
              required
              autoFocus
              disabled={pending}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-neutral-900 outline-none focus:border-[#1A73E8] focus:ring-1 focus:ring-[#1A73E8]"
            />
            <p className="mt-1 text-xs text-neutral-500">{ayuda}</p>
            {state.error && <p className="mt-1 text-xs text-red-600">{state.error}</p>}
          </div>
          <button
            type="submit"
            disabled={pending}
            className="shrink-0 rounded-lg bg-[#1A73E8] px-3 py-2 text-xs font-medium text-white transition hover:bg-[#1558b0] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending ? "..." : "Guardar"}
          </button>
          <button
            type="button"
            onClick={() => setEditando(false)}
            disabled={pending}
            className="shrink-0 rounded-lg border border-neutral-300 px-3 py-2 text-xs font-medium text-neutral-700 transition hover:bg-neutral-50"
          >
            Cancelar
          </button>
        </form>
      )}
    </div>
  );
}
