# overlay — HUD de telemetría JOTE LV-X7030

Fork customizado de [flighthud](https://github.com/jfromaniello/flighthud) que genera un
overlay de video transparente (ProRes 4444 alpha) a partir del log CSV del Garmin GDU 460.

## Templates disponibles

| Template | Descripción |
|----------|-------------|
| `jote_cockpit` | PFD completo: horizon artificial, speed tape, altímetro, VSI, heading rose, EIS, OAT |
| `jote_EIS` | Solo panel EIS + velocímetro circular (IAS) + variómetro circular (VSI) |

## Setup

```bash
cd overlay
pip install uv
uv sync
```

## Render

```bash
# Preview rápido (8 seg)
uv run flighthud ruta/al/log.csv -o ruta/frames --offset 500 --duration 8 -t jote_cockpit -j 4

# Render completo
uv run flighthud ruta/al/log.csv -o ruta/frames --offset 0 --duration 1250 -t jote_cockpit -j 6

# Encode a ProRes 4444 alpha
ffmpeg -y -framerate 30 -i ruta/frames/frame_%06d.png \
  -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 \
  overlay.mov
```

## Widgets customizados

- **`eis_panel`** (`widgets/eis.py`): panel EIS compacto estilo Garmin G3X —
  MAP/RPM (diales circulares), FUEL/OIL/TEMP (barras), EGT×4, CHT, AMPS, FLAP, VOLTS.
- **`dial_gauge`** (`widgets/eis.py`): dial circular standalone en estilo EIS —
  mismo look que MAP/RPM, configurable con `vmin/vmax/bands/start/sweep`.

## Ícono del avión

`assets/aircraft_icon.png` — vista superior JOTE, se auto-recorta al bounding-box
no-transparente para centrarse correctamente en la heading rose.
