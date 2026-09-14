# Microservicio de análisis de marcha

FastAPI que expone el algoritmo del notebook (`../Codigo_analisis_marcha_con_IMU.ipynb`) como
un endpoint HTTP. Pensado para desplegarse en **Render** (free tier, sin tarjeta), manteniendo
el código portable a **Google Cloud Run** para migrar más adelante sin reescribir nada — ver
"Desplegar" más abajo.

## Estado actual (actualizado 2026-09-14)

**En producción real, con cliente real.** Desplegado en Render (`imu-analizer.onrender.com`),
llamado por el frontend en Vercel. Validado end-to-end con CSV reales del sensor (no solo la señal
sintética de los tests) — incluido un bug real de producción encontrado y corregido el 2026-09-14
(ver `analysis.py`, sección "Pierna derecha vs. izquierda" abajo): la celda 13 del notebook
(ajuste automático de sentido del eje Z) no corría en producción, así que el resultado no
reproducía Colab exacto para algunas grabaciones. 11 tests automatizados (`pytest`), todos pasan.

Lo que **sigue faltando** (sin cambios desde 2026-09-11, ver también "Pendientes" al final):

- CORS abierto (`allow_origins=["*"]`) y sin autenticación entre Next.js y el microservicio —
  cualquiera con la URL puede pegarle a `/analyze` directo. Pendiente restringir al dominio real
  de Vercel antes de manejar datos de más pacientes/clientes.
- No lee `csv_url` (Supabase Storage), solo recibe el archivo subido directo (`multipart/form-data`).
- No se probó el build de `Dockerfile` localmente en ninguna sesión del asistente (sandbox sin
  permisos sobre Docker) — pero el deploy real a Render sí funciona, así que esto ya no bloquea
  nada, es solo una verificación local que quedó sin hacer.

## Endpoints

- `GET /health` — liveness check.
- `POST /analyze` — recibe un CSV del sensor Xsens DOT (`multipart/form-data`, campo `file`) más
  parámetros opcionales:
  - `pierna`: `"derecha"` (default) o `"izquierda"`.
  - `alpha`, `umbral_balanceo_deg_s`, `umbral_tc_deg_s`, `distancia_min_balanceo_s`,
    `distancia_min_minimos_s`: parámetros del filtro/detección de eventos, default igual al
    notebook.

  Devuelve JSON con: parámetros usados, frecuencia de muestreo detectada, `deteccion_lado`
  (método usado / pierna declarada / si se invirtió la señal), eventos (índices y tiempos de
  balanceo, contacto inicial, contacto terminal) y métricas (duración de ciclo, tiempo de apoyo,
  tiempo de balanceo, cadencia).

  Errores devuelven HTTP 422 con `{"detail": "..."}` (CSV sin columnas requeridas, señal sin
  suficientes eventos detectables, parámetros inválidos, pierna mal declarada, etc.)

- `POST /report` — recibe JSON `{"resultado": <la respuesta completa de /analyze>, "nombre_archivo":
  "opcional.csv"}` y devuelve un PDF (`application/pdf`, 2 páginas): página 1 el mismo gráfico de
  "Detección de eventos de marcha" que el notebook (celda 20, recortado y normalizado) más un
  encabezado con metadata; página 2 una tabla de métricas por ciclo + los promedios/cadencia. No
  vuelve a correr el algoritmo — solo necesita el JSON que ya devolvió `/analyze` (o el guardado en
  `analysis_results.raw_json` en Supabase), así que no hace falta el CSV original de nuevo. Usa
  `matplotlib` (backend `Agg`, sin display) — ver `report.py`.

- `GET /docs` — Swagger UI interactivo (probar el endpoint desde el navegador, generado
  automáticamente por FastAPI).

## Pierna derecha vs. izquierda

El notebook original se grabó con el sensor en la pierna **derecha**. Los datos de la pierna
**izquierda** quedan verticalmente en espejo (signo invertido) respecto a los de la derecha.

**Corregido 2026-09-14** (con CSV reales del cliente): `analysis.py` invierte la señal cruda
cuando `pierna="izquierda"`, y además el ajuste automático de sentido de la celda 13 del
notebook (invertir si `|min| > |max|` en la señal filtrada) corre **siempre**, sin excepción —
igual que en Colab, donde no era opcional. Antes ese ajuste vivía detrás de una variable de
entorno (`METODO_DETECCION_LADO`, ya retirada) que en producción lo dejaba apagado, así que
`pierna=derecha` no reproducía Colab exacto para grabaciones donde ese ajuste sí disparaba —
exactamente lo que reportó el cliente (marcha invertida).

Por construcción matemática, este ajuste automático cancela cualquier inversión previa
(`canonicalize(x) == canonicalize(-x)` siempre), así que en la práctica el parámetro `pierna`
ya no cambia el resultado del análisis para ningún archivo — queda solo como dato declarado/de
registro. Se decidió mantenerlo en la UI por ahora (decisión del usuario, 2026-09-14).

Cada respuesta de `/analyze` incluye `deteccion_lado` para auditar qué pasó en cada análisis.

## Requisitos

- Python 3.11+ (el `Dockerfile` usa 3.11-slim; localmente sirve cualquier 3.11/3.12).
- El sistema debe permitir crear un entorno virtual (`python3 -m venv`). En Ubuntu/Debian, si
  falta, instalar los dos paquetes (el segundo es el que trae `ensurepip`, que es el que realmente
  falla si no está):

  ```bash
  sudo apt install python3-venv python3.12-venv   # el número de versión debe matchear tu python3 -V
  ```

  (Alternativa sin instalar nada a nivel sistema: `pip install --user --break-system-packages -r
  requirements-dev.txt` instala todo en tu carpeta de usuario. Funciona, pero `venv` es más
  prolijo porque aísla las dependencias del proyecto — usalo si podés instalar el paquete de
  arriba.)

## Correr localmente

```bash
cd microservice
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # incluye requirements.txt + pytest/httpx
uvicorn main:app --reload
```

El servidor queda en `http://localhost:8000`. Con `--reload` se reinicia solo al guardar cambios
en el código, útil mientras desarrollás.

Para elegir el método de detección de lado en local, copiar `.env.example` a `.env`:

```bash
cp .env.example .env
```

## Cómo probar

### 1. Automatizado (recomendado primero)

```bash
pytest tests/ -v
```

Corre 13 tests: 7 contra el algoritmo directo (`analysis.py`) y 6 contra el endpoint HTTP real
(`main.py`, vía `FastAPI TestClient`, sin necesidad de levantar `uvicorn` a mano). Usan una señal
de marcha sintética (`tests/conftest.py`) — no necesitan ningún CSV externo. Cubren: detección de
ciclos en pierna derecha, corrección exacta de pierna izquierda (ambos métodos), pierna mal
declarada, parámetros inválidos, CSV inválido/corto, y los endpoints `/health` y `/analyze`.

### 2. Manual con curl, contra el servidor real

Con el servidor corriendo (`uvicorn main:app --reload`) y un CSV real del sensor a mano:

```bash
curl -F "file=@ruta/al/sensor.csv" -F "pierna=derecha" http://localhost:8000/analyze
```

Health check:

```bash
curl http://localhost:8000/health
```

### 3. Manual desde el navegador (Swagger UI)

Con el servidor corriendo, abrir `http://localhost:8000/docs`: permite subir un CSV y mandar el
request desde la UI sin usar curl, y muestra el schema completo de request/response.

### 4. Generar un CSV sintético para probar sin sensor real

Si todavía no tenés un CSV real a mano, `tests/conftest.py` tiene la función que genera una señal
de marcha sintética. Para exportarla a un archivo y probarla con curl/Swagger:

```bash
python3 -c "
from tests.conftest import _construir_gyr_z, _construir_dataframe
df = _construir_dataframe(_construir_gyr_z())
df.to_csv('/tmp/sensor_sintetico.csv', index=False)
print('/tmp/sensor_sintetico.csv generado')
"
curl -F "file=@/tmp/sensor_sintetico.csv" -F "pierna=derecha" http://localhost:8000/analyze
```

## Correr con Docker (mismo entorno que producción)

```bash
docker build -t imu-microservice .
docker run -p 8080:8080 --env-file .env imu-microservice
curl -F "file=@ruta/al/sensor.csv" http://localhost:8080/analyze
```

Si tu usuario no está en el grupo `docker`, vas a necesitar `sudo docker ...`, o agregarte al
grupo una vez (`sudo usermod -aG docker $USER`, requiere cerrar sesión y volver a entrar).

## Desplegar

El `Dockerfile` es la única fuente de verdad para el deploy (no hay buildpacks ni configuración
específica de una plataforma): cualquier runtime que sepa construir la imagen y respetar la
variable de entorno `$PORT` sirve. Hoy se despliega en **Render**; **Cloud Run** queda documentado
abajo como ruta de migración para cuando haya una tarjeta que GCP acepte — cambiar de plataforma
no debería requerir tocar código, solo repetir el deploy en la otra.

### Render (actual)

Requiere una cuenta de Render (no pide tarjeta para el free tier) y el repo pusheado a GitHub/GitLab.

1. En el dashboard de Render: **New → Web Service**, conectar el repo.
2. **Root Directory**: `microservice` (el `Dockerfile` está ahí, no en la raíz del repo).
3. **Environment**: `Docker` (Render detecta el `Dockerfile` automáticamente).
4. **Instance Type**: Free.
5. No hace falta agregar variables de entorno propias (ver `.env.example`). Render setea `PORT`
   automáticamente; el `Dockerfile` ya lo respeta (`${PORT}`), no hace falta configurarlo a mano.
6. Deploy. Al terminar, Render da la URL pública (`https://<servicio>.onrender.com`) — esa es la
   URL que usará el backend de Next.js para llamar a `/analyze`.

Notas:

- El servicio free duerme tras ~15 min de inactividad; el primer request tras dormir tarda
  ~30-50s en responder (cold start). Es una limitación conocida y aceptada mientras no haya
  presupuesto/tarjeta para un tier pago o para Cloud Run.
- El CORS en `main.py` está abierto (`allow_origins=["*"]`) — restringir al dominio real del
  frontend antes de producción.

### Cloud Run (migración futura)

Requiere `gcloud` CLI instalado y autenticado, y un proyecto de GCP con facturación habilitada
(tarjeta válida cargada, aunque el uso se mantenga dentro del free tier — este fue justamente el
paso que falló la última vez que se intentó).

```bash
gcloud auth login
gcloud config set project TU_PROYECTO_ID
gcloud run deploy imu-microservice \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

`gcloud run deploy --source .` construye la imagen con Cloud Build y la despliega, sin que haga
falta pushear manualmente a un registry. El free tier cubre 2M requests/mes, 360,000 GB-seg de
memoria y 180,000 vCPU-seg — de sobra para este uso, y con cold starts mucho más cortos que
Render. `--allow-unauthenticated` deja el endpoint público; para restringir a que solo el backend
de Next.js lo llame, usar autenticación con cuenta de servicio (`--no-allow-unauthenticated` +
IAM invoker) en vez de depender solo de CORS.

## Pendientes

- Restringir CORS al dominio real del frontend (`allow_origins=["*"]` sigue abierto).
- Autenticación entre el backend de Next.js y este microservicio (o dejarlo público si el riesgo
  es aceptable para el caso de uso).
- Endpoint que lea el CSV desde una URL firmada de Supabase Storage en vez de (o además de) recibir
  el archivo subido directo.
- Calibrar los umbrales default contra más CSV reales a medida que el cliente mande más (solo se
  probaron 2 hasta ahora, ver `analysis.py`).

Ya resuelto (no repetir): `/report` (PDF) está deployado y probado en Render; se probó con CSV
reales del sensor (derecha e izquierda); el deploy a Render funciona de punta a punta en
producción real.
