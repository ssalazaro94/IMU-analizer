"""Tests unitarios del algoritmo (sin pasar por HTTP)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import DatosInsuficientesError, analizar_marcha  # noqa: E402


def test_pierna_derecha_detecta_ciclos(df_marcha_derecha: pd.DataFrame):
    resultado = analizar_marcha(df_marcha_derecha, pierna="derecha")

    assert len(resultado["eventos"]["indices_contacto_inicial"]) >= 10
    assert len(resultado["eventos"]["indices_contacto_terminal"]) >= 9
    assert resultado["metricas"]["duracion_promedio_ciclo_s"] == pytest.approx(1.1, abs=0.05)


def test_pierna_izquierda_reproduce_derecha(
    df_marcha_derecha: pd.DataFrame, df_marcha_izquierda: pd.DataFrame
):
    """Declarar la pierna correcta (o no) da el mismo resultado: el ajuste
    automático de sentido del eje Z (igual que la celda 13 del notebook)
    siempre corre y por construcción matemática cancela cualquier inversión
    previa — canonicalize(x) == canonicalize(-x) sin importar el signo de
    entrada. Ver analysis.py para el detalle."""
    r_derecha = analizar_marcha(df_marcha_derecha, pierna="derecha")
    r_izquierda = analizar_marcha(df_marcha_izquierda, pierna="izquierda")

    assert r_izquierda["eventos"]["indices_contacto_inicial"] == r_derecha["eventos"]["indices_contacto_inicial"]
    assert r_izquierda["eventos"]["indices_contacto_terminal"] == r_derecha["eventos"]["indices_contacto_terminal"]
    assert r_izquierda["metricas"]["cadencia_promedio_pasos_min"] == pytest.approx(
        r_derecha["metricas"]["cadencia_promedio_pasos_min"]
    )


def test_pierna_mal_declarada_da_el_mismo_resultado_correcto(df_marcha_izquierda: pd.DataFrame):
    """El ajuste automático de sentido hace que declarar mal la pierna ya no
    produzca métricas incorrectas ni falle: converge al mismo resultado que
    declararla bien (ver test anterior). Esto es distinto del comportamiento
    previo a 2026-09-14 (declarar mal la pierna fallaba con 422)."""
    bien = analizar_marcha(df_marcha_izquierda, pierna="izquierda")
    mal = analizar_marcha(df_marcha_izquierda, pierna="derecha")

    assert mal["eventos"]["indices_contacto_inicial"] == bien["eventos"]["indices_contacto_inicial"]
    assert mal["metricas"]["cadencia_promedio_pasos_min"] == pytest.approx(
        bien["metricas"]["cadencia_promedio_pasos_min"]
    )


def test_pierna_invalida_lanza_value_error(df_marcha_derecha: pd.DataFrame):
    with pytest.raises(ValueError):
        analizar_marcha(df_marcha_derecha, pierna="ambas")


def test_csv_muy_corto_lanza_datos_insuficientes():
    df = pd.DataFrame({"SampleTimeFine": [0, 16667], "Gyr_Z": [0.0, 1.0]})
    with pytest.raises(DatosInsuficientesError):
        analizar_marcha(df)
