# LV-X7030 JOTE IFR — Sistema de seguimiento de telemetría

Análisis sistemático de los datos de vuelo del LV-X7030 JOTE, avión experimental de
construcción propia (motor Rotax 912 ULS, aviónica Garmin G3X Touch), actualmente en
fase de ensayos en vuelo en el Aeródromo Alta Gracia, Córdoba.

## Qué hace

Después de cada vuelo se descarga el log CSV del GDU 460 (tarjeta SD). Este proyecto lo
procesa contra los límites mandatorios de los manuales de a bordo — Rotax OM 912 Ed.4,
Manual JOTE rev.1, G3X Touch Pilot's Guide, Manual de Ensayos en Vuelo — y genera un
reporte técnico con:

- Parámetros fuera de límite
- Tendencias entre vuelos
- Alertas CAS acumuladas
- Comparación entre vuelos

El análisis incorpora el contexto específico del aeródromo: elevación oficial 1.748 ft MSL,
AGL calculado sobre Pressure Altitude (neutraliza variaciones de QNH), y el desnivel de
48 ft entre cabeceras de pista.

## Qué se monitorea

**Motor:** RPM (cigüeñal directo), temperaturas de aceite y refrigerante, presión de aceite,
EGTs por cilindro, presión y flujo de combustible, voltaje/amperaje del alternador, MAP vs
curva teórica del manual.

**Vuelo:** IAS vs límites del manual JOTE (VNE/VNO/VA), velocidad sobre el suelo, AGL real,
tasa vertical, VLOF en ensayos de carrera.

**Aviónica:** alertas CAS segundo a segundo, HDG MISCOMP, diferencia altimétrica G5 vs G3X.

## Para qué sirve

Detectar anomalías antes de que se conviertan en problemas, documentar tendencias a lo
largo del programa de ensayos, y generar reportes técnicos listos para taller — con datos
y comparaciones, **sin diagnósticos** (esa parte es trabajo de los técnicos).

## Setup rápido (cualquier PC)

```bash
git clone https://github.com/hernansans/jote-telemetry.git
cd jote-telemetry
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                       # tiene que mostrar todos los tests en verde
```

Los logs CSV del GDU 460 van en `tests/fixtures/` (gitignoreados, no se suben al repo).

## Módulos

### `analyzer/` — análisis post-vuelo híbrido (Python + LLM)
Motor "v2" integrado desde [jote-analyzer](https://github.com/jfromaniello/jote-analyzer):
fases de vuelo, límites condicionales (presión de aceite por RPM, EGT/MAP, factor de carga,
viento cruzado, flaps inferidos) y reporte narrativo generado por LLM (OpenAI), con gráficos
y exportación a PDF. Ver [`analyzer/README.md`](analyzer/README.md).

### `src/` — análisis de telemetría (v1, legado)
Parser del CSV del GDU 460 + motor de comparación simple contra límites mandatorios.
Se mantiene por ahora como referencia; `analyzer/` lo supera en alcance.

### `overlay/` — HUD de video
Fork customizado de [flighthud](https://github.com/jfromaniello/flighthud) que genera un
overlay de video transparente (ProRes 4444 alpha) a partir del mismo CSV.
Se compone sobre el video del vuelo en el editor — mismo log, dos usos.

Ver [`overlay/README.md`](overlay/README.md) para instrucciones de render.

## Roadmap

- [x] Parser de CSV del GDU 460
- [x] Motor de comparación contra límites (`docs/limites.yaml`)
- [x] HUD overlay de video (ProRes 4444 alpha) — módulo `overlay/`
- [x] Generador de reportes Markdown por vuelo (LLM) — módulo `analyzer/`
- [x] Comparación entre vuelos / tendencias — módulo `analyzer/` (multi-log)
- [ ] Web app: subir CSV → recibir reporte + overlay por descarga
- [ ] Seguimiento de horas de motor, vencimientos, gastos operativos, mantenimiento

## Estructura del repo

```
analyzer/  análisis post-vuelo híbrido (Python + LLM) — fases, límites condicionales, reportes
docs/      límites mandatorios (YAML, v1) y contexto del aeródromo — fuente de verdad legado
memory/    decisiones, hallazgos recurrentes entre vuelos
overlay/   HUD de video — fork flighthud con widgets y templates JOTE
src/       parser y motor de límites v1 (legado, ver analyzer/)
tests/     casos de prueba con CSVs de ejemplo
reports/   reportes generados por src/, uno por vuelo
```

## Flujo de trabajo

`main` está protegido. Todo cambio entra vía Pull Request revisado, una rama por feature.
