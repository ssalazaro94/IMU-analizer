"""Tests de integración sobre el endpoint HTTP real (FastAPI TestClient)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_analyze_pierna_derecha(csv_marcha_derecha: bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sensor.csv", csv_marcha_derecha, "text/csv")},
        data={"pierna": "derecha"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deteccion_lado"]["pierna_declarada"] == "derecha"
    assert len(body["eventos"]["indices_contacto_inicial"]) >= 10
    assert body["metricas"]["cadencia_promedio_pasos_min"] is not None


def test_analyze_pierna_izquierda(csv_marcha_izquierda: bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sensor.csv", csv_marcha_izquierda, "text/csv")},
        data={"pierna": "izquierda"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deteccion_lado"]["inversion_aplicada"] is True


def test_analyze_pierna_mal_declarada_devuelve_422(csv_marcha_izquierda: bytes):
    r = client.post(
        "/analyze",
        files={"file": ("sensor.csv", csv_marcha_izquierda, "text/csv")},
        data={"pierna": "derecha"},
    )
    assert r.status_code == 422


def test_analyze_csv_sin_columnas_requeridas_devuelve_422():
    csv_invalido = b"col1,col2\n1,2\n"
    r = client.post("/analyze", files={"file": ("sensor.csv", csv_invalido, "text/csv")})
    assert r.status_code == 422
    assert "SampleTimeFine" in r.json()["detail"]


def test_analyze_sin_archivo_devuelve_422():
    r = client.post("/analyze")
    assert r.status_code == 422
