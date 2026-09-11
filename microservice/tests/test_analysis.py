"""Tests unitarios del algoritmo (sin pasar por HTTP)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import DatosInsuficientesError, analizar_marcha  # noqa: E402


def test_pierna_derecha_detecta_ciclos(df_marcha_derecha: pd.DataFrame):
    resultado = analizar_marcha(df_marcha_derecha, pierna="derecha", metodo_deteccion_lado="pierna")

    assert len(resultado["eventos"]["indices_contacto_inicial"]) >= 10
    assert len(resultado["eventos"]["indices_contacto_terminal"]) >= 9
    assert resultado["metricas"]["duracion_promedio_ciclo_s"] == pytest.approx(1.1, abs=0.05)
    assert resultado["deteccion_lado"]["inversion_aplicada"] is False


def test_pierna_izquierda_con_metodo_pierna_reproduce_derecha(
    df_marcha_derecha: pd.DataFrame, df_marcha_izquierda: pd.DataFrame
):
    """La corrección determinista por pierna debe deshacer el espejo exactamente."""
    r_derecha = analizar_marcha(df_marcha_derecha, pierna="derecha", metodo_deteccion_lado="pierna")
    r_izquierda = analizar_marcha(df_marcha_izquierda, pierna="izquierda", metodo_deteccion_lado="pierna")

    assert r_izquierda["eventos"]["indices_contacto_inicial"] == r_derecha["eventos"]["indices_contacto_inicial"]
    assert r_izquierda["eventos"]["indices_contacto_terminal"] == r_derecha["eventos"]["indices_contacto_terminal"]
    assert r_izquierda["metricas"]["cadencia_promedio_pasos_min"] == pytest.approx(
        r_derecha["metricas"]["cadencia_promedio_pasos_min"]
    )
    assert r_izquierda["deteccion_lado"]["inversion_aplicada"] is True


def test_pierna_izquierda_con_metodo_auto_tambien_corrige(df_marcha_izquierda: pd.DataFrame):
    resultado = analizar_marcha(df_marcha_izquierda, pierna="izquierda", metodo_deteccion_lado="auto")

    assert len(resultado["eventos"]["indices_contacto_inicial"]) >= 10
    assert resultado["deteccion_lado"]["inversion_aplicada"] is True


def test_pierna_declarada_mal_falla_en_vez_de_dar_metricas_incorrectas(df_marcha_izquierda: pd.DataFrame):
    with pytest.raises(DatosInsuficientesError):
        analizar_marcha(df_marcha_izquierda, pierna="derecha", metodo_deteccion_lado="pierna")


def test_pierna_invalida_lanza_value_error(df_marcha_derecha: pd.DataFrame):
    with pytest.raises(ValueError):
        analizar_marcha(df_marcha_derecha, pierna="ambas")


def test_metodo_deteccion_lado_invalido_lanza_value_error(df_marcha_derecha: pd.DataFrame):
    with pytest.raises(ValueError):
        analizar_marcha(df_marcha_derecha, metodo_deteccion_lado="promedio")


def test_csv_muy_corto_lanza_datos_insuficientes():
    df = pd.DataFrame({"SampleTimeFine": [0, 16667], "Gyr_Z": [0.0, 1.0]})
    with pytest.raises(DatosInsuficientesError):
        analizar_marcha(df)
