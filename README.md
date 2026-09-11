# IMU-analizer

Análisis de marcha (gait analysis) a partir de datos de un sensor IMU **Xsens DOT**
(cuaterniones, acelerómetro, giroscopio), con detección de eventos del ciclo de marcha
(contacto inicial, contacto terminal, balanceo medio) y cálculo de métricas clínicas
(duración de ciclo, tiempo de apoyo, tiempo de balanceo, cadencia).

## Estado actual

El análisis vive hoy en un notebook de Google Colab:
[`Codigo_analisis_marcha_con_IMU.ipynb`](./Codigo_analisis_marcha_con_IMU.ipynb).

Pipeline:
1. Carga de un CSV exportado del sensor Xsens DOT.
2. Filtro pasa-altas (forward-backward) sobre el eje Z del giroscopio para remover deriva.
3. Detección de eventos de marcha (`scipy.signal.find_peaks`): balanceo medio, contacto inicial
   y contacto terminal del pie.
4. Recorte/normalización de la señal al primer y último ciclo completo detectado.
5. Cálculo de métricas: duración de ciclo, tiempo de apoyo, tiempo de balanceo y cadencia
   (pasos/min).

## En construcción: aplicación web

El objetivo es envolver este análisis en una aplicación web con:
- Login de usuarios.
- Subida de archivos CSV del sensor, con análisis automático.
- Un hub donde ver los archivos subidos y sus resultados.
- Una sección para ajustar los parámetros del análisis (umbrales de detección de eventos, etc.).

**Stack planeado:**
- Next.js (TypeScript) desplegado en Vercel — frontend y API.
- Supabase — autenticación, base de datos (Postgres) y almacenamiento de archivos.
- Un microservicio en Python (FastAPI + numpy/scipy/pandas) que reutiliza el algoritmo del
  notebook para procesar cada CSV subido.

## Estructura del repo

- `Codigo_analisis_marcha_con_IMU.ipynb` — notebook con el algoritmo de análisis de referencia.
