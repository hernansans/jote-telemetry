# Integración de jote-analyzer como `analyzer/`

## Qué es

[jote-analyzer](https://github.com/jfromaniello/jote-analyzer) es un motor de análisis
post-vuelo del JOTE escrito por Hernán a partir del trabajo de este repo: tomó
`docs/limites.yaml` (creado acá) y lo enriqueció con más contenido extraído de los mismos
manuales (Rotax OM 912 Ed.4, Manual JOTE rev.1). Se integró como módulo `analyzer/`
(2026-06-09), siguiendo el mismo patrón que `overlay/` (fork externo incorporado como
submódulo de funcionalidad, no reemplazo destructivo).

## Enfoque híbrido (por qué importa)

- **Python determinístico** (`analyzer/src/jote_analyzer/analysis.py` +
  `phases.py`): calcula todo lo numérico — excursiones, picos, duraciones, fases de vuelo —
  contra `analyzer/data/limites.yaml`. Esto es "autoritativo", el LLM no puede inventar
  números.
- **LLM (OpenAI, gpt-4.1)**: recibe el JSON de hallazgos + `limites.yaml` + docs de contexto
  y redacta el reporte narrativo siguiendo `analyzer/prompts/analisis_vuelo.md`.

## Qué cierra de pendientes previos

- **Presión de aceite condicional por RPM** — exactamente lo que quedó documentado como TODO
  en `memory/presion-aceite-analisis.md`: RPM<3500 → mín 11.6 psi; RPM≥3500 → 29-72.5 psi
  normal, hasta 101.5 psi transitorio en arranque en frío.
- **Fases de vuelo automáticas** — máquina de estados (rodaje/despegue/ascenso/crucero/
  descenso/toque/aterrizaje) basada en AGL (Pressure Altitude − referencia de pista
  detectada), tasa vertical y velocidad. Mismo principio de "referencia de pista detectada"
  que ya usábamos manualmente para oil pressure.
- **Diagnóstico de motor**: dispersión EGT entre cilindros, relación MAP/RPM.
- **Envolvente de vuelo**: factor de carga (g) condicionado a flaps, maniobras prohibidas
  (alabeo/cabeceo), VFE condicionado a flaps inferidos del sensor crudo.
- **Viento cruzado** en despegue/aterrizaje vs 15 kt demostrado.
- **Límites de planificación** (peso, CG, puertas, combustible) — no monitoreables desde
  telemetría, pero documentados en `limites.yaml` y listados como checklist en el reporte.
- **Reportes Markdown/PDF generados por vuelo** y **comparación entre vuelos** — cierran dos
  ítems del roadmap de este repo.

## Decisiones de la integración

- `src/` y `docs/limites.yaml` (v1) **se mantienen por ahora** como legado/referencia — no se
  borraron. `analyzer/` los supera en alcance.
- `analyzer/data/limites.yaml` es la fuente de verdad **vigente**. Si se corrige un límite,
  aplicar ahí primero (y opcionalmente replicar en `docs/limites.yaml` si `src/` sigue en
  uso).
- La API key de OpenAI **nunca se pega en el chat**: se crea `analyzer/.env` local
  (gitignored) a partir de `analyzer/.env.example`, mismo criterio que con el PAT de GitHub.
- `analyzer/reports/` está gitignoreado salvo `.gitkeep` — igual que `reports/` del repo
  principal: la data de vuelo y los reportes generados no se versionan.

## Cómo correrlo

```bash
cd analyzer
uv sync
cp .env.example .env   # completar OPENAI_KEY a mano, nunca en el chat
uv run jote-analyzer --data data --log /ruta/al/log.csv
```

`--no-llm` para solo el análisis determinístico (gratis, sin llamar a OpenAI).
`--pdf` para exportar PDF (requiere `uv sync --extra pdf`).
