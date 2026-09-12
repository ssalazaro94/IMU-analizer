# Infraestructura — IMU Analizer

Documento de referencia de toda la infraestructura real del proyecto: qué servicio hace qué, cómo
se conectan entre sí, y dónde tocar cada cosa. Mantenerlo actualizado cuando cambie algo de esto
(no hace falta actualizarlo por cambios de código de la aplicación en sí).

## Vista general

```
Usuario (navegador)
      │
      ▼
Next.js (Vercel) ──────────────► Supabase
  - Auth (login/logout)            - Postgres (profiles, equation_settings,
  - Route Handlers                   files, analysis_results)
    /api/analyze                   - Auth (email/password)
    /api/reanalyze                 - Storage (bucket csv-uploads, privado)
    /api/report                    - Realtime (status de files/analysis_results)
      │
      ▼
Microservicio FastAPI (Render) ◄── llamado desde los Route Handlers de Next.js
  - POST /analyze  (algoritmo de análisis de marcha)
  - POST /report   (PDF con gráficas + métricas)
  - GET  /health
```

El notebook original (`Codigo_analisis_marcha_con_IMU.ipynb`, Google Colab) es el origen del
algoritmo pero **no forma parte de la infraestructura en producción** — el microservicio es el
puerto de ese código a un servicio HTTP reutilizable.

## Repositorio

- GitHub: `ssalazaro94/IMU-analizer` (rama `main`).
- Monorepo con tres carpetas independientes en cuanto a deploy:
  - `frontend/` → Vercel.
  - `microservice/` → Render.
  - `supabase/` → no se "despliega"; son las migraciones SQL versionadas del proyecto de Supabase.
- Cada plataforma de deploy (Render, Vercel) apunta al mismo repo pero con **Root Directory**
  configurado a la subcarpeta correspondiente — no hay nada especial de monorepo tooling (turborepo,
  nx, etc.), son simplemente proyectos independientes que comparten repo.

## Supabase (DB + Auth + Storage + Realtime)

| Dato | Valor |
|---|---|
| Organización | `ssalazaro94's Org` (id/slug `ozhwewpyjoywwackprog`) |
| Proyecto | `imu-analizer` |
| Project ref | `qybvicgpaaznpjpatdzi` |
| Región | `sa-east-1` (São Paulo) |
| URL | `https://qybvicgpaaznpjpatdzi.supabase.co` |
| Dashboard | https://supabase.com/dashboard/project/qybvicgpaaznpjpatdzi |

**Por qué Supabase:** Postgres + Auth + Storage + Realtime en un solo servicio gratuito, evita
armar cada pieza por separado.

### Autenticación

- Email + contraseña (sin magic link).
- **No hay pantalla de registro todavía** — los usuarios se crean a mano desde el dashboard
  (Authentication → Users → Add user, marcando "Auto Confirm User") o vía la Admin API con la
  `service_role` key.
- Roles: tabla `profiles` (`id` = `auth.users.id`, `role` en `('root', 'admin')`).
  - Un trigger (`on_auth_user_created`) crea automáticamente el perfil con `role='admin'` al
    registrarse un usuario nuevo.
  - `root` puede editar los parámetros globales del algoritmo y todo lo que puede hacer `admin`.
  - `admin` solo puede subir archivos, ver resultados, re-analizar y descargar reportes.
  - Función helper `public.is_root()` (`security definer`) usada en las policies de RLS para
    evitar recursión al consultar el propio rol.
  - Alta de un `root` o cambio de rol: **manual**, vía SQL (`update public.profiles set role =
    'root' where id = '<uuid>'`) — no hay UI para gestionar roles todavía.

### Cómo agregar un usuario nuevo

No hay pantalla de registro en la app — se hace a mano desde el dashboard de Supabase:

1. **Crear el usuario**: dashboard de Supabase (https://supabase.com/dashboard/project/qybvicgpaaznpjpatdzi)
   → **Authentication → Users → Add user**. Cargar email y contraseña, y tildar **"Auto Confirm
   User"** (si no, el usuario queda sin confirmar y no puede loguearse hasta verificar el email).
2. **El rol se asigna solo**: el trigger `on_auth_user_created` crea automáticamente la fila en
   `profiles` con `role = 'admin'` apenas se crea el usuario en `auth.users`. No hace falta hacer
   nada más si el usuario va a ser `admin` (subir CSV, ver resultados, re-analizar, descargar
   reportes).
3. **Si el usuario necesita ser `root`** (además de lo anterior, puede editar los parámetros
   globales del algoritmo en `equation_settings`): ir a **SQL Editor** en el dashboard y correr:
   ```sql
   update public.profiles set role = 'root' where id = (
     select id from auth.users where email = 'el-email-del-usuario@ejemplo.com'
   );
   ```
4. **Listo**: el usuario ya puede entrar en `/login` con el email y la contraseña que se le cargó
   en el paso 1.

### Esquema de base de datos

Definido en `supabase/migrations/20260911190000_esquema_inicial.sql` (escrito de forma
idempotente: `create table if not exists`, `drop policy if exists` + `create policy`).

- **`profiles`**: `id`, `role`, `created_at`.
- **`equation_settings`**: fila única (`id = 1`), parámetros **globales** del algoritmo (`alpha`,
  `umbral_balanceo_deg_s`, `umbral_tc_deg_s`, `distancia_min_balanceo_s`,
  `distancia_min_minimos_s`, `metodo_deteccion_lado`). Defaults iguales al notebook original.
  Solo `root` puede modificarla (RLS).
- **`files`**: un archivo CSV subido (`uploaded_by`, `nombre_original`, `storage_path`, `pierna`,
  `status` en `pending | processing | done | error`, `error_message`).
- **`analysis_results`**: un resultado de análisis (`file_id`, `parametros_usados`,
  `deteccion_lado`, métricas resumidas, `raw_json` con la respuesta completa del microservicio).
  **Cada corrida (incluyendo "volver a analizar") inserta una fila nueva** — no se pisa el
  historial, queda como auditoría.
- RLS (actualizado 2026-09-12, migración `20260912190000_restringir_visibilidad_admin.sql`):
  **`root` ve todos los archivos y resultados; `admin` solo ve los que él mismo subió**
  (`uploaded_by = auth.uid()`). `analysis_results` hereda la visibilidad del `files` asociado (por
  `file_id`, no por `created_by`, porque quien re-analiza no es necesariamente el uploader
  original). El bucket `csv-uploads` sigue el mismo criterio vía la carpeta `<user_id>/...` en la
  que ya se guarda cada CSV. No hace falta tocar el frontend: las queries no tienen `.eq(...)` de
  usuario, dependen enteramente de RLS (incluida la suscripción de Realtime, que respeta RLS por
  usar el cliente browser con la sesión del usuario, no `service_role`).
- Realtime habilitado sobre `files` y `analysis_results` (`alter publication supabase_realtime add
  table ...`) — así el frontend se entera de cambios de estado sin hacer polling.

**Cómo se aplican las migraciones:** con la contraseña directa de Postgres descartada a propósito
(se generó al azar al crear el proyecto y nunca se guardó en ningún lado), las migraciones se
corren así:

```bash
supabase link --project-ref qybvicgpaaznpjpatdzi
supabase db query --linked -f supabase/migrations/<archivo>.sql
```

Esto ejecuta el SQL vía la Management API de Supabase (usa el access token de la sesión de
`supabase login`, no la contraseña de la DB). `supabase db push` (el camino "normal" del CLI) SÍ
pide esa contraseña — si en algún momento se quiere usar ese camino, hay que resetear la
contraseña desde el dashboard (Project Settings → Database → Reset database password) primero.

### Storage

- Bucket **`csv-uploads`**, privado (no público).
- Los CSV originales se guardan en `<user_id>/<uuid>.csv` para poder re-analizarlos sin volver a
  subirlos (botón "Volver a analizar").
- Policies: cualquier autenticado puede subir a su propia carpeta (`<user_id>/...`) y leer
  cualquier objeto del bucket (mismo criterio de "workspace compartido" que las tablas); solo
  `root` puede borrar.

## Render (microservicio de análisis)

| Dato | Valor |
|---|---|
| URL pública | https://imu-analizer.onrender.com |
| Root Directory en Render | `microservice` |
| Deploy | Docker (usa `microservice/Dockerfile` directamente, sin buildpack propietario) |
| Plan | Free — duerme tras ~15 min de inactividad, cold start de ~30-50s en el primer request |

**Por qué Render:** GCP Cloud Run era la opción preferida (cold starts más cortos) pero GCP
rechazó todas las tarjetas del usuario al intentar activar facturación, así que se volvió a
Render (no pide tarjeta para el free tier). El código se mantiene deliberadamente portable a
Cloud Run (Dockerfile como única fuente de verdad, respeta `$PORT`) por si más adelante se
consigue una tarjeta que funcione — ver "Notas de portabilidad" abajo.

### Variables de entorno en Render

- `METODO_DETECCION_LADO` = `pierna` (default; alternativa: `auto`, la heurística original del
  notebook — ambos métodos conviven en `analysis.py`).

### Endpoints

- `GET /health`
- `POST /analyze` — recibe el CSV + parámetros, devuelve el JSON completo del análisis.
- `POST /report` — recibe el JSON que ya devolvió `/analyze` (no vuelve a correr el algoritmo) y
  devuelve un PDF de 2 páginas (gráfico igual al del notebook + tabla de métricas por ciclo).
  Requiere `matplotlib` (agregado a `requirements.txt` — instalar siempre desde
  `requirements-dev.txt`/`requirements.txt` completo, nunca suelto, porque arrastra una versión de
  numpy incompatible con el `scipy` pinneado si se instala aislado).

### Notas de portabilidad (Render → Cloud Run)

- El `Dockerfile` es la única fuente de verdad del build/runtime; respeta `$PORT`.
- No se usan add-ons propietarios de Render.
- Variables de entorno vía `os.environ` estándar, sin SDK de Render.
- `microservice/README.md` documenta ambos paths de deploy (Render actual, Cloud Run como
  migración futura con el mismo `Dockerfile`).

### Pendiente / riesgos conocidos del microservicio

- CORS abierto (`allow_origins=["*"]`) — restringir al dominio real del frontend antes de
  exponerlo con datos reales de pacientes.
- Sin autenticación entre Next.js y el microservicio (cualquiera que tenga la URL puede pegarle).
- No se probó todavía con un CSV real del sensor de punta a punta (recién se está calibrando —
  ver `microservice/scripts/diagnosticar_csv.py`, un script nuevo para diagnosticar por qué un CSV
  real no detecta suficientes eventos de marcha con los umbrales default).
- No se probó el build de Docker localmente (el entorno del asistente no tiene permisos sobre
  Docker) ni un deploy de punta a punta iniciado desde cero por el asistente — el servicio ya
  estaba desplegado y se verificó que responde correctamente (`/health`, `/analyze`, `/report`)
  pero el proceso de creación del servicio en Render lo hizo el usuario a mano desde el dashboard.

## Vercel (frontend)

**Todavía no desplegado** — el frontend solo se probó corriendo local (`pnpm dev`) contra el
proyecto real de Supabase y (para `/report`) contra el microservicio corriendo local o en Render.

Configuración ya preparada para cuando se cree el proyecto en Vercel:

- **Root Directory**: `frontend` (monorepo — hay que fijarlo a mano en la config del proyecto de
  Vercel, no se puede desde `vercel.json`).
- `frontend/vercel.json`: fija `framework: nextjs` y los comandos (`pnpm install` / `pnpm build`).
- Variables de entorno a cargar en Project Settings → Environment Variables (nunca en
  `vercel.json`):
  - `NEXT_PUBLIC_SUPABASE_URL` = `https://qybvicgpaaznpjpatdzi.supabase.co`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = la publishable key del proyecto (ver dashboard de Supabase
    → Project Settings → API; también está en `frontend/.env.local`, que no está commiteado).
  - `NEXT_PUBLIC_ANALYSIS_SERVICE_URL` = `https://imu-analizer.onrender.com` en producción (en
    local se puede apuntar a `http://localhost:8000` mientras se prueba el microservicio sin
    depender de Render).

### Riesgo conocido, no validado en producción

Los tres Route Handlers que llaman al microservicio (`/api/analyze`, `/api/reanalyze`,
`/api/report`) usan `after()` de Next.js para correr la llamada al microservicio **después** de
responderle al cliente (necesario por el cold start de Render, de hasta ~30-50s, para no bloquear
la respuesta al navegador). En Vercel, `after()` depende del límite de duración/`waitUntil` de la
función (`maxDuration` está seteado a 60s en esas rutas) — no se probó todavía si esto alcanza en
el plan real de Vercel una vez desplegado. Si falla en producción, la alternativa es aumentar
`maxDuration`/cambiar de plan, o mover el disparo del análisis a una cola real en vez de `after()`.

## Flujo de subida y análisis (async)

1. El usuario sube un CSV desde `/` (Next.js) → `POST /api/analyze`.
2. El Route Handler: sube el CSV a Storage (`csv-uploads`), inserta una fila en `files`
   (`status = 'pending'`), y devuelve `202` de inmediato con el `file_id`.
3. En background (`after()`), llama a `POST /analyze` del microservicio en Render con el CSV y los
   parámetros globales actuales (leídos de `equation_settings`).
4. Al terminar, inserta una fila en `analysis_results` y actualiza `files.status` a `done` o
   `error` (+ `error_message` si falló).
5. El frontend está suscripto a `postgres_changes` de Supabase Realtime sobre `files` y
   `analysis_results`, así que la UI se actualiza sola sin recargar ni hacer polling.
6. "Volver a analizar" repite el mismo flujo pero descargando el CSV original desde Storage en vez
   de pedir que se vuelva a subir, y agrega una fila nueva a `analysis_results` (no pisa la
   anterior).
7. "Descargar reporte (PDF)" (`POST /api/report`) lee la fila más reciente de `analysis_results`
   (su `raw_json`) y se la manda al microservicio (`POST /report`), que genera el PDF sin volver a
   correr el algoritmo.

## Desarrollo local

```bash
# Microservicio
cd microservice
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload            # http://localhost:8000

# Frontend (en otra terminal)
cd frontend
pnpm install
cp .env.local.example .env.local     # completar con las credenciales reales de Supabase
pnpm dev                             # http://localhost:3000
```

Con `NEXT_PUBLIC_ANALYSIS_SERVICE_URL=http://localhost:8000` en `.env.local` se puede probar todo
el flujo (incluido `/report`) sin depender de que Render esté despierto ni de tener esa versión
del microservicio ya deployada ahí.

## Resumen de lo que falta (a nivel infraestructura, no de features de producto)

- Crear el proyecto en Vercel y cargar las env vars.
- Restringir CORS del microservicio al dominio real de Vercel una vez exista.
- Definir autenticación entre Next.js y el microservicio (hoy el endpoint es público).
- Validar `after()`/`maxDuration` en Vercel real contra el cold start de Render.
- Calibrar los umbrales default del algoritmo contra CSV reales del sensor (en curso).
