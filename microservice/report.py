"""Genera el PDF de reporte a partir del resultado de ``analizar_marcha``.

El gráfico de la página 1 replica a propósito, tal cual, el de la celda 20 de
``Codigo_analisis_marcha_con_IMU.ipynb`` (señal recortada/normalizada con los
eventos de marcha marcados) — es el gráfico que el usuario pidió que se vea
igual al del notebook. La página 2 agrega una tabla de métricas por ciclo que
el notebook solo imprimía por consola (celdas 21-25).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")  # sin display, solo para generar el PDF en el servidor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def _pagina_grafico(pdf: PdfPages, resultado: dict, nombre_archivo: str | None) -> None:
    eventos = resultado["eventos"]
    tiempo = eventos["tiempo_normalizado_s"]
    senal = eventos["senal_filtrada"]
    idx_balanceo = eventos["indices_balanceo"]
    idx_ic = eventos["indices_contacto_inicial"]
    idx_tc = eventos["indices_contacto_terminal"]

    fig = plt.figure(figsize=(14, 8))
    ax = fig.add_axes((0.08, 0.08, 0.88, 0.68))

    ax.plot(tiempo, senal, label="Señal filtrada (recortada y normalizada)")
    ax.scatter(
        [tiempo[i] for i in idx_balanceo],
        [senal[i] for i in idx_balanceo],
        color="green",
        label="Balanceo",
    )
    ax.scatter(
        [tiempo[i] for i in idx_ic],
        [senal[i] for i in idx_ic],
        color="red",
        label="Contacto incial pie",
    )
    ax.scatter(
        [tiempo[i] for i in idx_tc],
        [senal[i] for i in idx_tc],
        color="blue",
        label="Contacto terminal pie",
    )
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Velocidad angular (deg/s)")
    ax.set_title("Detección de eventos de marcha")
    ax.legend()
    ax.grid(True)

    deteccion = resultado["deteccion_lado"]
    parametros = resultado["parametros"]
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    encabezado = (
        "Reporte de análisis de marcha — Análisis de Marcha IMU\n"
        f"Archivo: {nombre_archivo or '(sin nombre)'}    "
        f"Pierna: {deteccion['pierna_declarada']}    "
        f"Frecuencia de muestreo: {resultado['frecuencia_muestreo_hz']:.2f} Hz    "
        f"Generado: {generado}\n"
        f"Parámetros — alpha: {parametros['alpha']}, umbral balanceo: "
        f"{parametros['umbral_balanceo_deg_s']} deg/s, umbral TC: "
        f"{parametros['umbral_tc_deg_s']} deg/s, distancia mín. balanceo: "
        f"{parametros['distancia_min_balanceo_s']} s, distancia mín. mínimos: "
        f"{parametros['distancia_min_minimos_s']} s (método de lado: {deteccion['metodo']})"
    )
    fig.text(0.08, 0.94, encabezado, ha="left", va="top", fontsize=9, family="monospace")

    pdf.savefig(fig)
    plt.close(fig)


def _pagina_metricas(pdf: PdfPages, resultado: dict) -> None:
    metricas = resultado["metricas"]
    duracion_ciclo = metricas["duracion_ciclo_s"]
    tiempos_apoyo = metricas["tiempos_apoyo_s"]
    tiempos_balanceo = metricas["tiempos_balanceo_s"]

    n_filas = max(len(duracion_ciclo), len(tiempos_apoyo), len(tiempos_balanceo))

    def _celda(valores: list[float], i: int) -> str:
        return f"{valores[i]:.4f}" if i < len(valores) else "—"

    filas = [
        [str(i + 1), _celda(duracion_ciclo, i), _celda(tiempos_apoyo, i), _celda(tiempos_balanceo, i)]
        for i in range(n_filas)
    ]

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.axis("off")
    ax.set_title("Métricas de marcha por ciclo", fontsize=13, loc="left", pad=20)

    tabla = ax.table(
        cellText=filas,
        colLabels=["Ciclo", "Duración (s)", "Tiempo de apoyo (s)", "Tiempo de balanceo (s)"],
        loc="upper center",
        cellLoc="center",
        bbox=(0.05, 0.35, 0.9, 0.55),
    )
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(9)

    def _fmt(valor: float | None, sufijo: str) -> str:
        return f"{valor:.4f} {sufijo}" if valor is not None else "—"

    resumen = (
        f"Duración promedio de ciclo: {_fmt(metricas['duracion_promedio_ciclo_s'], 's')}\n"
        f"Tiempo promedio de apoyo: {_fmt(metricas['tiempo_promedio_apoyo_s'], 's')}\n"
        f"Tiempo promedio de balanceo: {_fmt(metricas['tiempo_promedio_balanceo_s'], 's')}\n"
        f"Cadencia promedio: {_fmt(metricas['cadencia_promedio_pasos_min'], 'pasos/min')}"
    )
    fig.text(0.08, 0.25, resumen, ha="left", va="top", fontsize=11)

    pdf.savefig(fig)
    plt.close(fig)


def generar_pdf(resultado: dict, nombre_archivo: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        _pagina_grafico(pdf, resultado, nombre_archivo)
        _pagina_metricas(pdf, resultado)
    return buffer.getvalue()
