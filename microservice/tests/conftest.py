"""Fixtures compartidas: generan un CSV sintético con forma de señal de marcha
(no hay ningún CSV real del sensor en el repo todavía)."""

import io

import numpy as np
import pandas as pd
import pytest

FRECUENCIA_MUESTREO_HZ = 60.0
DURACION_S = 12.0
CICLO_S = 1.1


def _construir_gyr_z(signo_balanceo: float = -80.0, signo_contacto: float = 35.0) -> np.ndarray:
    """Construye un Gyr_Z sintético de ~10 ciclos de marcha.

    Los signos por default están elegidos para que, tras pasar por el filtro
    pasa-altas forward-backward del notebook (que responde de forma asimétrica
    a pulsos aislados), el resultado quede con el balanceo dominando en
    positivo — la misma convención de "pierna derecha" que usa el resto del
    pipeline. Invertir el signo del array resultante simula una pierna
    izquierda (espejo vertical).
    """
    n = int(DURACION_S * FRECUENCIA_MUESTREO_HZ)
    gyr_z = np.zeros(n)
    for c in np.arange(0.3, DURACION_S, CICLO_S):
        idx_balanceo = int(c * FRECUENCIA_MUESTREO_HZ)
        idx_ic = int((c + 0.35) * FRECUENCIA_MUESTREO_HZ)
        idx_tc_prev = int((c - 0.15) * FRECUENCIA_MUESTREO_HZ)
        for i in range(n):
            gyr_z[i] += signo_balanceo * np.exp(-0.5 * ((i - idx_balanceo) / 3) ** 2)
            gyr_z[i] += signo_contacto * np.exp(-0.5 * ((i - idx_ic) / 3) ** 2)
            gyr_z[i] += signo_contacto * np.exp(-0.5 * ((i - idx_tc_prev) / 3) ** 2)
    gyr_z += np.random.default_rng(0).normal(0, 0.5, n)
    return gyr_z


def _construir_dataframe(gyr_z: np.ndarray) -> pd.DataFrame:
    n = len(gyr_z)
    t = np.arange(n) / FRECUENCIA_MUESTREO_HZ
    return pd.DataFrame(
        {
            "PacketCounter": np.arange(n),
            "SampleTimeFine": (t * 1_000_000).astype(np.int64),
            "Quat_W": 1.0,
            "Quat_X": 0.0,
            "Quat_Y": 0.0,
            "Quat_Z": 0.0,
            "Acc_X": 0.0,
            "Acc_Y": 0.0,
            "Acc_Z": 9.8,
            "Gyr_X": 0.0,
            "Gyr_Y": 0.0,
            "Gyr_Z": gyr_z,
        }
    )


@pytest.fixture
def df_marcha_derecha() -> pd.DataFrame:
    return _construir_dataframe(_construir_gyr_z())


@pytest.fixture
def df_marcha_izquierda(df_marcha_derecha: pd.DataFrame) -> pd.DataFrame:
    espejo = df_marcha_derecha.copy()
    espejo["Gyr_Z"] = -espejo["Gyr_Z"]
    return espejo


@pytest.fixture
def csv_marcha_derecha(df_marcha_derecha: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df_marcha_derecha.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def csv_marcha_izquierda(df_marcha_izquierda: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df_marcha_izquierda.to_csv(buf, index=False)
    return buf.getvalue()
