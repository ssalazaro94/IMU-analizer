"""Microservicio FastAPI que expone el análisis de marcha a partir de un CSV
de un sensor Xsens DOT. Pensado para desplegarse en Render (o cualquier
runtime que respete la variable de entorno ``PORT``, como Cloud Run)."""

import io
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis import (
    METODOS_DETECCION_LADO_VALIDOS,
    DatosInsuficientesError,
    analizar_marcha,
    cargar_csv,
)
from report import generar_pdf

load_dotenv()  # no-op si no hay .env (ej. en Render/Cloud Run, donde las env vars se setean directo)

METODO_DETECCION_LADO = os.getenv("METODO_DETECCION_LADO", "pierna")
if METODO_DETECCION_LADO not in METODOS_DETECCION_LADO_VALIDOS:
    raise RuntimeError(
        f"METODO_DETECCION_LADO={METODO_DETECCION_LADO!r} inválido. "
        f"Debe ser uno de {METODOS_DETECCION_LADO_VALIDOS}."
    )

app = FastAPI(title="IMU Analizer - Microservicio de análisis de marcha")

# TODO: restringir a los orígenes reales del frontend antes de producción.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    pierna: str = Form("derecha"),
    alpha: float = Form(0.995),
    umbral_balanceo_deg_s: float = Form(50.0),
    umbral_tc_deg_s: float = Form(-20.0),
    distancia_min_balanceo_s: float = Form(0.5),
    distancia_min_minimos_s: float = Form(0.3),
) -> dict:
    contenido = await file.read()

    try:
        df = cargar_csv(io.BytesIO(contenido))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    try:
        return analizar_marcha(
            df,
            alpha=alpha,
            umbral_balanceo_deg_s=umbral_balanceo_deg_s,
            umbral_tc_deg_s=umbral_tc_deg_s,
            distancia_min_balanceo_s=distancia_min_balanceo_s,
            distancia_min_minimos_s=distancia_min_minimos_s,
            pierna=pierna,
            metodo_deteccion_lado=METODO_DETECCION_LADO,
        )
    except (DatosInsuficientesError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error))


class _Parametros(BaseModel):
    alpha: float
    umbral_balanceo_deg_s: float
    umbral_tc_deg_s: float
    distancia_min_balanceo_s: float
    distancia_min_minimos_s: float


class _DeteccionLado(BaseModel):
    metodo: str
    pierna_declarada: str
    inversion_aplicada: bool


class _Eventos(BaseModel):
    tiempo_normalizado_s: list[float]
    senal_filtrada: list[float]
    indices_balanceo: list[int]
    indices_contacto_inicial: list[int]
    indices_contacto_terminal: list[int]


class _Metricas(BaseModel):
    duracion_ciclo_s: list[float]
    duracion_promedio_ciclo_s: float | None = None
    tiempos_apoyo_s: list[float]
    tiempo_promedio_apoyo_s: float | None = None
    tiempos_balanceo_s: list[float]
    tiempo_promedio_balanceo_s: float | None = None
    cadencia_promedio_pasos_min: float | None = None


class ResultadoAnalisis(BaseModel):
    """Debe matchear exactamente el dict que devuelve ``analizar_marcha`` (POST /analyze)."""

    parametros: _Parametros
    frecuencia_muestreo_hz: float
    deteccion_lado: _DeteccionLado
    eventos: _Eventos
    metricas: _Metricas


class ReportRequest(BaseModel):
    resultado: ResultadoAnalisis
    nombre_archivo: str | None = None


@app.post("/report")
def report(body: ReportRequest) -> Response:
    pdf_bytes = generar_pdf(body.resultado.model_dump(), nombre_archivo=body.nombre_archivo)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reporte_marcha.pdf"'},
    )
