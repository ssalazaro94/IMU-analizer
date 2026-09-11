# Frontend — Análisis de Marcha IMU

Next.js (App Router, TypeScript, Tailwind) + Supabase Auth. Por ahora solo está implementado el
login (email/contraseña); el resto de las vistas (subida de CSV, hub de archivos, configuración)
está diseñado como boceto en Stitch pero todavía no tiene código.

## Requisitos

- Node 24+, **pnpm** (no usar npm/yarn en este proyecto).
- Un proyecto de Supabase creado dentro de la organización **`ssalazaro94`** en supabase.com.

## Configuración local

```bash
cd frontend
pnpm install
cp .env.local.example .env.local   # completar con los valores reales de Supabase
pnpm dev
```

Variables de entorno (`.env.local`):

- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Project Settings → API en el
  dashboard de Supabase.
- `NEXT_PUBLIC_ANALYSIS_SERVICE_URL`: URL del microservicio de análisis
  (`https://imu-analizer.onrender.com` en producción).

## Estructura relevante

- `src/lib/supabase/{client,server}.ts`: clientes de Supabase para Client/Server Components.
- `src/proxy.ts` + `src/lib/supabase/proxy.ts`: refresco de sesión y protección de rutas (Next.js
  16 renombró `middleware.ts` a `proxy.ts`; el export debe llamarse `proxy`, no `middleware`).
- `src/app/login/`: página y server action de login.
- `src/app/actions.ts`: server action de logout, usada desde `src/app/page.tsx`.

## Deploy en Vercel

Este repo es un monorepo (`frontend/` + `microservice/`), así que al crear el proyecto en Vercel
hay que configurar:

- **Root Directory**: `frontend`
- Variables de entorno: las mismas tres de arriba, cargadas en Project Settings → Environment
  Variables (no en el `vercel.json`, que no lleva secretos).

`vercel.json` en esta carpeta ya fija `framework: nextjs` y los comandos con `pnpm`.

## Pendiente

- Registro de usuarios (por ahora los usuarios se crean a mano desde el dashboard de Supabase).
- Vista de subida de CSV, hub de archivos y configuración de parámetros (bocetos ya hechos en
  Stitch, proyecto "IMU Análisis de Marcha").
- Gráficas del resultado con ECharts, mostrando solo desde la señal recortada/normalizada del
  notebook en adelante (ver `.claude_context.md` en la raíz del repo).
