# analyzer — análisis post-vuelo híbrido (Python + LLM)

Motor de análisis "v2" del JOTE, integrado desde
[jote-analyzer](https://github.com/jfromaniello/jote-analyzer). Reemplaza en alcance a
`src/limits_engine.py` (que se mantiene por ahora como referencia/legado) e incorpora
fases de vuelo, límites condicionales, diagnósticos de motor y reportes narrativos
generados por LLM.

## Enfoque híbrido

1. **Python (determinístico):** lee el CSV del GDU 460 y compara contra `data/limites.yaml`.
   Detecta excursiones, ventanas temporales, picos y alertas CAS con **números exactos**.
   Nunca depende del LLM para los cálculos numéricos. Salida: `reports/hallazgos_<log>.json`.
2. **LLM (OpenAI):** recibe esos hallazgos + `limites.yaml` + docs de contexto y redacta el
   **análisis narrativo** (interpretación, tendencias, recomendaciones) siguiendo
   [`prompts/analisis_vuelo.md`](prompts/analisis_vuelo.md).

## Qué suma respecto de `src/`

- **Fases del vuelo** (rodaje/despegue/ascenso/crucero/descenso/toque/aterrizaje) detectadas
  con una máquina de estados; cada hallazgo se contextualiza con la fase en que ocurrió.
- **Altura sobre pista** calculada con referencia de presión detectada del propio vuelo
  (neutraliza el QNH del día) — ver `data/docs/aerodromo.md`.
- **Presión de aceite con límites condicionales por RPM** (RPM<3500 → mín 11.6 psi;
  RPM≥3500 → 29-72.5 psi normal, hasta 101.5 psi transitorio en arranque en frío). Esto
  cierra el TODO documentado en `memory/presion-aceite-analisis.md`.
- **Diagnóstico de motor:** dispersión de EGT entre cilindros y relación MAP/RPM (detección
  de anomalías).
- **Inferencia de flaps** desde el sensor crudo (sin calibración), habilitando VFE y
  envolvente de carga condicionados a flaps.
- **Envolvente de vuelo:** factor de carga (g) y maniobras prohibidas (alabeo/cabeceo).
- **Viento cruzado** estimado en despegue/aterrizaje (límite 15 kt demostrado).
- **Límites de planificación** (peso, CG, puertas, combustible) documentados en
  `data/limites.yaml` aunque no sean monitoreables desde el log; el reporte los lista como
  checklist de planificación/inspección previa.
- **Reportes narrativos** en markdown (y opcionalmente PDF) generados por OpenAI, con
  gráficos (strip chart + scatter MAP/RPM) embebidos.

## Setup

```bash
cd analyzer
uv sync                # base
uv sync --extra pdf    # opcional, para exportar a PDF (--pdf)
cp .env.example .env   # completar OPENAI_KEY a mano (NUNCA commitear .env)
```

`.env` ya está en `.gitignore`. Pegá tu `OPENAI_KEY` directamente en el archivo local,
nunca en el chat ni en el repo.

## Uso

```bash
# Un vuelo
uv run jote-analyzer --data data --log /ruta/al/log.csv

# Comparar varios vuelos (tendencias)
uv run jote-analyzer --data data --log vuelo1.csv --log vuelo2.csv

# Solo el análisis determinístico, sin llamar al LLM (rápido y gratis)
uv run jote-analyzer --data data --log log.csv --no-llm

# Generar también el PDF (requiere: uv sync --extra pdf)
uv run jote-analyzer --data data --log log.csv --pdf
```

### Salidas (en `analyzer/reports/`)

- `hallazgos_<log>.json` — hallazgos determinísticos (trazabilidad, siempre).
- `report_<log>.md` — reporte narrativo del LLM (si no se usa `--no-llm`).
- `report_<log>.pdf` — versión PDF (solo con `--pdf`).
- `chart_<log>_perfil.png` — strip chart del vuelo (sombreado por fase, líneas de límite).
- `chart_<log>_map_rpm.png` — scatter MAP vs RPM coloreado por fase (diagnóstico).

## Estructura

```
analyzer/
├── data/
│   ├── limites.yaml   # fuente de verdad: límites con cita de manual+página (versionado)
│   └── docs/          # contexto (aeródromo) — se manda al LLM
├── prompts/           # prompt del sistema para el LLM (editable sin tocar código)
├── assets/            # CSS para el PDF
├── src/jote_analyzer/ # código del análisis (fases, límites, charts, llm, cli)
└── reports/           # salidas generadas (gitignored, salvo .gitkeep)
```

Los logs CSV, PDFs de manuales y reportes generados NO van al repo (`.gitignore`). Solo se
versiona `data/limites.yaml`, `data/docs/` y los prompts.

## Origen

`data/limites.yaml` es el `docs/limites.yaml` original de este repo, enriquecido con
contenido extraído de los manuales (Rotax OM 912 Ed.4, Manual JOTE rev.1) por
[jote-analyzer](https://github.com/jfromaniello/jote-analyzer). Cuando se actualicen los
límites, considerar sincronizar ambos archivos o, eventualmente, dejar `data/limites.yaml`
como única fuente de verdad y deprecar `docs/limites.yaml`.
