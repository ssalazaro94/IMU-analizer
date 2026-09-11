"""Microservicio FastAPI que expone el análisis de marcha a partir de un CSV
de un sensor Xsens DOT. Pensado para desplegarse en Render (o cualquier
runtime que respete la variable de entorno ``PORT``, como Cloud Run)."""

import io
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analysis import (
    METODOS_DETECCION_LADO_VALIDOS,
    DatosInsuficientesError,
    analizar_marcha,
    cargar_csv,
)

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
