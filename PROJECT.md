# JOTE Telemetry — guía para Claude

Sistema de seguimiento de telemetría del LV-X7030 JOTE (experimental, Rotax 912 ULS,
Garmin G3X Touch), en ensayos en vuelo en Aeródromo Alta Gracia, Córdoba.

## Antes de analizar un log o escribir código

1. Para análisis de vuelo, usar `analyzer/` (motor v2, híbrido Python+LLM) — ver
   `analyzer/README.md`. `analyzer/data/limites.yaml` es la versión enriquecida y vigente.
2. `docs/limites.yaml` y `docs/aerodromo.md` son la versión v1/legado (referencia de
   `src/`); `analyzer/data/` es la fuente de verdad actual.
3. Leé `memory/MEMORY.md` — decisiones previas, hallazgos recurrentes entre vuelos, convenciones.

## Reglas del proyecto

- Los reportes comparan datos contra límites del manual. **No se hacen diagnósticos** —
  el reporte muestra "fuera de límite / dentro de límite" con valores y contexto, el técnico decide.
- AGL se calcula sobre Pressure Altitude (no altitud GPS) para neutralizar variaciones de QNH.
- Cualquier límite nuevo o corrección de límite existente debe citar manual + edición + página
  en `docs/limites.yaml`.
- Cambios a `main` solo vía PR revisado. Una rama por feature.

## Estructura

- `analyzer/` — motor v2: fases de vuelo, límites condicionales, reporte LLM, gráficos, PDF
- `src/` — parser de CSV del GDU 460, motor de comparación v1 (legado)
- `docs/` — límites estructurados v1 y contexto del aeródromo (legado)
- `memory/` — qué aprendimos vuelo a vuelo, decisiones de diseño
- `tests/` — casos con CSVs de ejemplo
- `reports/` — reportes generados por `src/`, uno por vuelo
- `overlay/` — HUD de video transparente (ProRes 4444 alpha) generado desde el mismo CSV

## Módulo analyzer

`analyzer/` es el motor de análisis post-vuelo integrado desde
[jote-analyzer](https://github.com/jfromaniello/jote-analyzer) (enfoque híbrido
Python determinístico + LLM narrativo). Antes de usarlo:

- Setup: `cd analyzer && uv sync && cp .env.example .env` y completar `OPENAI_KEY` a mano
  en el `.env` local (gitignored). **Nunca pegar la key en el chat ni commitearla.**
- Uso: `uv run jote-analyzer --data data --log /ruta/al/log.csv` (agregar `--no-llm` para
  solo el análisis determinístico, `--pdf` para exportar PDF).
- `analyzer/data/limites.yaml` es la fuente de verdad vigente de límites (enriquecida desde
  `docs/limites.yaml` con contenido de los manuales). Cualquier corrección de límites debería
  aplicarse ahí (y considerar sincronizar con `docs/limites.yaml` si se sigue usando `src/`).
- Detalle completo en `analyzer/README.md`.

## Módulo overlay

El módulo `overlay/` es un fork de flighthud con widgets y templates custom para el JOTE.
Antes de trabajar en él, leé `overlay/README.md` para el setup y comandos de render.

**Reglas clave del overlay:**
- Todo output (frames, .mov, logs) va a disco A: — nunca al repo ni a C:
- Los CSV de telemetría son datos privados — no se commitean
- Render completo: `-j 6` workers (más causa MemoryError por page file en C:)
- Templates activos: `jote_cockpit` (PFD completo), `jote_EIS` (EIS + IAS + VSI)
- Widgets custom en `overlay/src/flighthud/widgets/eis.py`: `eis_panel`, `dial_gauge`
