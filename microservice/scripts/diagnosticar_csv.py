"""Diagnóstico rápido para un CSV real que falla con
'No se detectaron suficientes contactos iniciales (IC)'.

Corre el mismo filtro/inversión que ``analysis.py`` pero sin exigir que se
arme un ciclo completo, e imprime los números clave para saber si el
problema es de calibración de umbrales o de pierna/orientación mal
declarada. También guarda un PNG de la señal filtrada completa.

Uso:
    python scripts/diagnosticar_csv.py ruta/al/sensor.csv --pierna derecha
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis import PIERNAS_VALIDAS, _filtrar_forward_backward, cargar_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--pierna", choices=PIERNAS_VALIDAS, default="derecha")
    parser.add_argument("--alpha", type=float, default=0.995)
    parser.add_argument("--umbral-balanceo-deg-s", type=float, default=50.0)
    parser.add_argument("--umbral-tc-deg-s", type=float, default=-20.0)
    parser.add_argument("--distancia-min-balanceo-s", type=float, default=0.5)
    parser.add_argument("--distancia-min-minimos-s", type=float, default=0.3)
    parser.add_argument("--salida-png", type=Path, default=Path("diagnostico_senal.png"))
    args = parser.parse_args()

    df = cargar_csv(args.csv_path)
    tiempo_segundos = df["SampleTimeFine"].to_numpy() / 1_000_000
    frecuencia_muestreo = 1 / float(np.mean(np.diff(tiempo_segundos)))

    gyr_z_crudo = df["Gyr_Z"].to_numpy(dtype=float)
    inversion_por_pierna = args.pierna == "izquierda"
    if inversion_por_pierna:
        gyr_z_crudo = -gyr_z_crudo

    gyr_z_filt = _filtrar_forward_backward(gyr_z_crudo, args.alpha)
    senal = -gyr_z_filt

    # Igual que la celda 13 del notebook: SIEMPRE corre (ver analysis.py).
    # Por construcción cancela matemáticamente cualquier inversión previa,
    # así que --pierna ya no cambia el resultado — se deja como dato
    # informativo/de registro únicamente.
    inversion_automatica = False
    if abs(np.min(senal)) > abs(np.max(senal)):
        senal = -senal
        inversion_automatica = True

    print(f"Muestras: {len(df)}  ·  Frecuencia estimada: {frecuencia_muestreo:.2f} Hz")
    print(f"Pierna declarada: {args.pierna}  ·  "
          f"inversión aplicada: {inversion_por_pierna or inversion_automatica}")
    print(f"Señal filtrada — min: {senal.min():.2f} deg/s, max: {senal.max():.2f} deg/s, "
          f"media: {senal.mean():.2f} deg/s\n")

    balanceo_medio, props = find_peaks(
        senal,
        height=args.umbral_balanceo_deg_s,
        distance=max(1, int(args.distancia_min_balanceo_s * frecuencia_muestreo)),
    )
    minimos_locales, _ = find_peaks(
        -senal, distance=max(1, int(args.distancia_min_minimos_s * frecuencia_muestreo))
    )
    print(f"Picos de 'balanceo' con umbral actual ({args.umbral_balanceo_deg_s} deg/s): "
          f"{len(balanceo_medio)}")
    print(f"Mínimos locales candidatos a IC/TC: {len(minimos_locales)}\n")

    print("Picos encontrados a distintos umbrales de balanceo (para calibrar):")
    max_abs = float(np.max(np.abs(senal)))
    for fraccion in (0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9):
        umbral_prueba = max_abs * fraccion
        n_picos, _ = find_peaks(
            senal,
            height=umbral_prueba,
            distance=max(1, int(args.distancia_min_balanceo_s * frecuencia_muestreo)),
        )
        print(f"  {umbral_prueba:7.2f} deg/s ({int(fraccion * 100)}% del máximo abs): "
              f"{len(n_picos)} picos")

    if len(balanceo_medio) == 0:
        print(
            "\n⚠ Con el umbral actual no hay NINGÚN pico de balanceo. Como el ajuste "
            "automático de sentido (celda 13) ya corrió, esto probablemente sea un problema "
            "de calibración de umbrales o de calidad de la señal, no de pierna/orientación "
            "(--pierna ya no afecta el resultado, ver docstring de analysis.py)."
        )

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(tiempo_segundos, senal, label="Señal filtrada (completa, sin recortar)")
    ax.axhline(args.umbral_balanceo_deg_s, color="green", linestyle="--", linewidth=1,
               label=f"Umbral balanceo actual ({args.umbral_balanceo_deg_s} deg/s)")
    ax.axhline(args.umbral_tc_deg_s, color="blue", linestyle="--", linewidth=1,
               label=f"Umbral TC actual ({args.umbral_tc_deg_s} deg/s)")
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Velocidad angular (deg/s)")
    ax.set_title("Diagnóstico: señal filtrada completa vs. umbrales configurados")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(args.salida_png, dpi=120)
    print(f"\nGráfico guardado en: {args.salida_png.resolve()}")


if __name__ == "__main__":
    main()
