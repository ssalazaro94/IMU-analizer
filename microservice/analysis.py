"""Algoritmo de análisis de marcha, portado desde
``Codigo_analisis_marcha_con_IMU.ipynb``.

Reutiliza tal cual la lógica del notebook (filtro pasa-altas forward-backward
sobre Gyr_Z + detección de eventos con ``scipy.signal.find_peaks``), con
cambios deliberados respecto al notebook original:

1. Se usa un único eje de tiempo derivado de ``SampleTimeFine`` en todo el
   pipeline (el notebook mezclaba ese eje con uno asumiendo 60 Hz fijos para
   el recorte final; ver ``.claude_context.md``).
2. Los umbrales/parámetros del filtro son argumentos, no constantes.
3. El notebook original se grabó con el sensor en la pierna derecha. Los
   datos de la pierna izquierda quedan verticalmente en espejo (signo
   invertido) respecto a los de la derecha, así que se invierte la señal
   cruda ANTES de filtrar cuando ``pierna="izquierda"``.

   IMPORTANTE (corregido 2026-09-14, con CSVs reales del cliente): el
   ajuste automático de sentido del eje Z de la celda 13 del notebook
   (invertir si ``|min| > |max|`` en la señal filtrada) **no es opcional
   en el notebook original — siempre corre**, sin importar la pierna. Antes
   este ajuste vivía detrás de un ``metodo_deteccion_lado`` configurable
   que en producción estaba en modo ``"pierna"`` (sin el ajuste automático),
   así que "derecha" nunca reproducía Colab exacto para grabaciones donde
   ese ajuste automático sí disparaba — la señal quedaba con la polaridad
   invertida, duplicando falsamente los eventos detectados (~2x la cadencia
   real). Se verificó con dos CSV reales del cliente (uno de cada pierna)
   que restaurar el ajuste automático como paso incondicional, sumado a la
   inversión previa por ``pierna`` para el lado izquierdo, reproduce
   exactamente los números de referencia del notebook para ambos archivos.
"""

from __future__ import annotations

from typing import BinaryIO, Union

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

COLUMNAS_REQUERIDAS = ["SampleTimeFine", "Gyr_Z"]
PIERNAS_VALIDAS = ("derecha", "izquierda")


class DatosInsuficientesError(Exception):
    """La señal no tiene suficientes eventos de marcha detectables."""


def filtro_pasa_altas(senal: np.ndarray, alpha: float = 0.995) -> np.ndarray:
    senal_filtrada = np.zeros_like(senal, dtype=float)
    for i in range(1, len(senal)):
        senal_filtrada[i] = senal[i] - senal[i - 1] + alpha * senal_filtrada[i - 1]
    return senal_filtrada


def _filtrar_forward_backward(senal: np.ndarray, alpha: float) -> np.ndarray:
    adelante = filtro_pasa_altas(senal, alpha)
    atras = filtro_pasa_altas(adelante[::-1], alpha)
    return atras[::-1]


def cargar_csv(fuente: Union[str, BinaryIO]) -> pd.DataFrame:
    df = pd.read_csv(fuente)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas requeridas en el CSV: {faltantes}")
    return df


def analizar_marcha(
    df: pd.DataFrame,
    alpha: float = 0.995,
    umbral_balanceo_deg_s: float = 50.0,
    umbral_tc_deg_s: float = -20.0,
    distancia_min_balanceo_s: float = 0.5,
    distancia_min_minimos_s: float = 0.3,
    pierna: str = "derecha",
) -> dict:
    if len(df) < 3:
        raise DatosInsuficientesError("El CSV no tiene suficientes muestras para analizar.")
    if pierna not in PIERNAS_VALIDAS:
        raise ValueError(f"pierna inválida: {pierna!r}. Debe ser una de {PIERNAS_VALIDAS}.")

    tiempo_segundos = df["SampleTimeFine"].to_numpy() / 1_000_000  # microsegundos -> segundos
    diffs = np.diff(tiempo_segundos)
    if np.any(diffs <= 0):
        raise ValueError(
            "SampleTimeFine no es estrictamente creciente; no se puede calcular la frecuencia de muestreo."
        )
    frecuencia_muestreo = 1 / float(np.mean(diffs))

    gyr_z_crudo = df["Gyr_Z"].to_numpy(dtype=float)

    # Inversión determinista según el lado declarado, ANTES de filtrar (el
    # filtro es lineal, así que invertir antes o después da lo mismo).
    inversion_por_pierna = pierna == "izquierda"
    if inversion_por_pierna:
        gyr_z_crudo = -gyr_z_crudo

    gyr_z_filt = _filtrar_forward_backward(gyr_z_crudo, alpha)
    gyr_z_filt = -gyr_z_filt

    senal = gyr_z_filt.copy()

    # Ajuste automático de sentido del eje Z, igual que la celda 13 del
    # notebook: SIEMPRE se aplica, sin importar la pierna declarada.
    inversion_automatica = False
    if abs(np.min(senal)) > abs(np.max(senal)):
        senal = -senal
        inversion_automatica = True

    balanceo_medio, _ = find_peaks(
        senal,
        height=umbral_balanceo_deg_s,
        distance=max(1, int(distancia_min_balanceo_s * frecuencia_muestreo)),
    )
    minimos_locales, _ = find_peaks(
        -senal, distance=max(1, int(distancia_min_minimos_s * frecuencia_muestreo))
    )

    contacto_inicial_pie: list[int] = []
    contacto_terminal_pie: list[int] = []
    for ms in balanceo_medio:
        minimos_antes = minimos_locales[minimos_locales < ms]
        minimos_despues = minimos_locales[minimos_locales > ms]

        if len(minimos_antes) > 0:
            tc = minimos_antes[-1]
            if senal[tc] < umbral_tc_deg_s:
                contacto_terminal_pie.append(int(tc))

        if len(minimos_despues) > 0:
            ic = minimos_despues[0]
            contacto_inicial_pie.append(int(ic))

    if len(contacto_inicial_pie) < 2:
        raise DatosInsuficientesError(
            "No se detectaron suficientes contactos iniciales (IC) para calcular un ciclo "
            "completo. Revisa los umbrales o la calidad de la señal."
        )

    primer_ic = contacto_inicial_pie[0]
    ultimo_ic = contacto_inicial_pie[-1]

    tiempo_recortado = tiempo_segundos[primer_ic : ultimo_ic + 1]
    senal_recortada = senal[primer_ic : ultimo_ic + 1]
    tiempo_normalizado = tiempo_recortado - tiempo_recortado[0] + 1

    def _recortar_indices(indices) -> list[int]:
        return [int(i) - primer_ic for i in indices if primer_ic <= i <= ultimo_ic]

    idx_balanceo = _recortar_indices(balanceo_medio)
    idx_ic = _recortar_indices(contacto_inicial_pie)
    idx_tc = _recortar_indices(contacto_terminal_pie)

    tiempos_ic = [float(tiempo_normalizado[i]) for i in idx_ic]
    tiempos_tc = [float(tiempo_normalizado[i]) for i in idx_tc]

    duracion_ciclo = [tiempos_ic[i] - tiempos_ic[i - 1] for i in range(1, len(tiempos_ic))]
    duracion_promedio_ciclo = float(np.mean(duracion_ciclo)) if duracion_ciclo else None

    tiempos_apoyo = []
    n_ciclos = min(len(tiempos_ic), len(tiempos_tc))
    for i in range(n_ciclos):
        if tiempos_tc[i] > tiempos_ic[i]:
            tiempos_apoyo.append(tiempos_tc[i] - tiempos_ic[i])
    tiempo_promedio_apoyo = float(np.mean(tiempos_apoyo)) if tiempos_apoyo else None

    tiempos_balanceo = []
    n_balanceos = min(len(tiempos_ic) - 1, len(tiempos_tc))
    for i in range(max(0, n_balanceos)):
        siguiente_ic = tiempos_ic[i + 1]
        siguiente_tc = tiempos_tc[i]
        if siguiente_ic > siguiente_tc:
            tiempos_balanceo.append(siguiente_ic - siguiente_tc)
    tiempo_promedio_balanceo = float(np.mean(tiempos_balanceo)) if tiempos_balanceo else None

    cadencia_promedio = (1 / duracion_promedio_ciclo) * 60 * 2 if duracion_promedio_ciclo else None

    return {
        "parametros": {
            "alpha": alpha,
            "umbral_balanceo_deg_s": umbral_balanceo_deg_s,
            "umbral_tc_deg_s": umbral_tc_deg_s,
            "distancia_min_balanceo_s": distancia_min_balanceo_s,
            "distancia_min_minimos_s": distancia_min_minimos_s,
        },
        "frecuencia_muestreo_hz": frecuencia_muestreo,
        "deteccion_lado": {
            "metodo": "pierna+auto",
            "pierna_declarada": pierna,
            "inversion_aplicada": inversion_por_pierna or inversion_automatica,
        },
        "eventos": {
            "tiempo_normalizado_s": tiempo_normalizado.tolist(),
            "senal_filtrada": senal_recortada.tolist(),
            "indices_balanceo": idx_balanceo,
            "indices_contacto_inicial": idx_ic,
            "indices_contacto_terminal": idx_tc,
        },
        "metricas": {
            "duracion_ciclo_s": duracion_ciclo,
            "duracion_promedio_ciclo_s": duracion_promedio_ciclo,
            "tiempos_apoyo_s": tiempos_apoyo,
            "tiempo_promedio_apoyo_s": tiempo_promedio_apoyo,
            "tiempos_balanceo_s": tiempos_balanceo,
            "tiempo_promedio_balanceo_s": tiempo_promedio_balanceo,
            "cadencia_promedio_pasos_min": cadencia_promedio,
        },
    }
