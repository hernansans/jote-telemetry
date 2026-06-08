# JOTE Telemetry — guía para Claude

Sistema de seguimiento de telemetría del LV-X7030 JOTE (experimental, Rotax 912 ULS,
Garmin G3X Touch), en ensayos en vuelo en Aeródromo Alta Gracia, Córdoba.

## Antes de analizar un log o escribir código

1. Leé `docs/limites.yaml` — límites mandatorios extraídos de los manuales (Rotax OM 912 Ed.4,
   Manual JOTE rev.1, G3X Touch Pilot's Guide, Manual de Ensayos en Vuelo).
2. Leé `docs/aerodromo.md` — contexto de Alta Gracia (elevación, AGL sobre Pressure Altitude,
   desnivel de pista).
3. Leé `memory/MEMORY.md` — decisiones previas, hallazgos recurrentes entre vuelos, convenciones.

## Reglas del proyecto

- Los reportes comparan datos contra límites del manual. **No se hacen diagnósticos** —
  el reporte muestra "fuera de límite / dentro de límite" con valores y contexto, el técnico decide.
- AGL se calcula sobre Pressure Altitude (no altitud GPS) para neutralizar variaciones de QNH.
- Cualquier límite nuevo o corrección de límite existente debe citar manual + edición + página
  en `docs/limites.yaml`.
- Cambios a `main` solo vía PR revisado. Una rama por feature.

## Estructura

- `src/` — parser de CSV del GDU 460, motor de comparación, generador de reportes
- `docs/` — límites estructurados y contexto del aeródromo (fuente de verdad para el análisis)
- `memory/` — qué aprendimos vuelo a vuelo, decisiones de diseño
- `tests/` — casos con CSVs de ejemplo
- `reports/` — reportes generados, uno por vuelo
