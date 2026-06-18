# overlay — HUD de telemetría JOTE LV-X7030

Fork customizado de [flighthud](https://github.com/jfromaniello/flighthud) que genera un
overlay de video transparente (ProRes 4444 alpha) a partir del log CSV del Garmin GDU 460.

## Templates disponibles

| Template | Descripción |
|----------|-------------|
| `jote_cockpit` | PFD completo: horizon artificial, speed tape, altímetro, VSI, heading rose, EIS, OAT |
| `jote_EIS` | Solo panel EIS + velocímetro circular (IAS) + variómetro circular (VSI) |
| `jote_info` | Panel de telemetría simple arriba a la derecha: GS, ALT (baro), V/S, TRACK, WIND |

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

# Panel simple (GS/ALT/V/S/TRACK/WIND) con la paleta JOTE — listo desde CLI
uv run flighthud ruta/al/log.csv -o ruta/frames -t jote_info -j 6

# Encode a ProRes 4444 alpha
ffmpeg -y -framerate 30 -i ruta/frames/frame_%06d.png \
  -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 \
  overlay.mov
```

### Render rápido: desacoplar render rate del framerate (`--render-fps`)

El HUD cambia lento, así que **no hace falta renderizar un frame único por cada
frame de salida**. Se renderizan `--render-fps` frames por segundo y ffmpeg los
**duplica** hasta `--fps` en la salida. El video final mantiene su duración y
framerate, pero se renderiza mucho más rápido.

El default es **`--render-fps 10`** (≈3× menos renders que 30 fps; divide exacto a
30, sin judder, y queda suave incluso con agujas/horizonte). Para un panel de solo
texto podés bajarlo más; para máxima fluidez en movimiento, igualarlo a `--fps`.

```bash
# Default: render @ 10 → video 30 fps (≈3× menos renders)
uv run flighthud log.csv -o overlay.mov -t jote_info --duration 3785 --fps 30 -j 6

# Panel de solo texto: aún más rápido
uv run flighthud log.csv -o overlay.mov -t jote_info --render-fps 5 -j 6

# Máxima fluidez (1:1, sin duplicación)
uv run flighthud log.csv -o overlay.mov -t jote_cockpit --render-fps 30 -j 6
```

- `--render-fps` se topea a `--fps` (renderizar de más no aporta nada).
- Para **salida a carpeta PNG**, los frames quedan a `--render-fps`; el CLI imprime
  el comando `ffmpeg` con el `-framerate` correcto para encodearlos a `--fps`.

### Codec del video (`--codec`)

Si la salida (`-o`) es `.mov` o `.webm`, el pipeline encodea el alpha solo (necesita
`ffmpeg`). El codec se elige por extensión salvo que pases `--codec`:

| Codec | Ext | ffmpeg | Notas |
|-------|-----|--------|-------|
| `prores4444` | `.mov` | `prores_ks -profile 4444 -pix_fmt yuva444p10le` | **Default de `.mov`.** Import confiable en DaVinci Resolve. |
| `qtrle` | `.mov` | `qtrle -pix_fmt argb` | Mucho más rápido y archivos chicos, pero **Resolve NO lo importa bien** — usalo solo para destinos no-Resolve (web / FCP / Premiere). |
| `vp9` | `.webm` | `libvpx-vp9 -pix_fmt yuva420p` | **Default de `.webm`.** |

```bash
# qtrle (rápido, NO para Resolve)
uv run flighthud log.csv -o overlay.mov -t jote_info --codec qtrle -j 6
```

> El editor del proyecto es **DaVinci Resolve**, que no importa qtrle de forma
> confiable. Para iterar rápido sin Resolve, lo más simple es la **secuencia PNG**
> (`-o carpeta/`) importada como image sequence.

## Widgets customizados

- **`eis_panel`** (`widgets/eis.py`): panel EIS compacto estilo Garmin G3X —
  MAP/RPM (diales circulares), FUEL/OIL/TEMP (barras), EGT×4, CHT, AMPS, FLAP, VOLTS.
- **`dial_gauge`** (`widgets/eis.py`): dial circular standalone en estilo EIS —
  mismo look que MAP/RPM, configurable con `vmin/vmax/bands/start/sweep`.
- **`eis_panel`** / **`dial_gauge`**: ver arriba.
- **`info_panel`** (`widgets/info_panel.py`): panel readout simple (réplica del
  HUD "simple" de joseflys /replay). Ver referencia completa abajo.

## Widget `info_panel`

Panel redondeado semitransparente con filas etiqueta-chica-atenuada sobre
valor-grande. **Anclado por su borde superior**: `x`,`y` son la esquina
superior-izquierda y el panel crece hacia abajo (al revés de los demás widgets,
que se anclan por la esquina inferior-izquierda). La altura se calcula sola según
la cantidad de filas.

El template `jote_info` ya viene con la paleta JOTE (blanco/gris/negro) y las
filas por defecto, listo para usar desde CLI (`-t jote_info`).

### Opciones del panel

| Clave | Default | Descripción |
|-------|---------|-------------|
| `x`, `y` | `0`, `0` | Esquina superior-izquierda del panel (px). `y` crece hacia arriba. |
| `width` | `230` | Ancho del panel (px). La altura es automática. |
| `rows` | ver abajo | Lista de filas (inline tables TOML). Si se omite, usa el set por defecto. |
| `pad` | `18` | Margen interno (px). |
| `label_size` | `10` | Tamaño de la etiqueta (pt). |
| `value_size` | `20` | Tamaño del valor (pt). |
| `label_gap` | `4` | Separación etiqueta→valor (px). |
| `row_gap` | `16` | Separación valor→siguiente etiqueta (px). |
| `radius` | `14` | Radio de las esquinas redondeadas (px). |
| `border_width` | `1.0` | Grosor del borde (`0` = sin borde). |
| `bg_color` | slate-900 @ 0.8 | Color de fondo, RGBA en 0–1. |
| `border_color` | slate-600 | Color del borde, RGBA en 0–1. |
| `label_color` | slate-400 | Color de las etiquetas, RGBA en 0–1. |
| `value_color` | `"white"` | Color de los valores (nombre matplotlib o RGBA 0–1). |
| `zorder` | `1` | Orden de apilado. |

### Opciones por fila

Cada entrada de `rows` es una inline table. Filas por defecto (si no se pasa
`rows`): **GS, ALT (baro), V/S, TRACK, WIND**.

| Clave | Default | Descripción |
|-------|---------|-------------|
| `label` | `""` | Texto de la etiqueta (se muestra en MAYÚSCULAS). |
| `kind` | `"value"` | `"value"` (lee `source`) o `"wind"` (combina dir + velocidad). |
| `source` | — | Columna del CSV (cualquiera de `NUMERIC_COLUMNS` en `data.py`). |
| `unit` | `""` | Sufijo, p.ej. `" KT"`, `" ft"`, `"°"`. |
| `decimals` | `0` | Cantidad de decimales. |
| `transform` | `"identity"` | `"fahrenheit_to_celsius"` o `"gph_to_lph"` para convertir unidades. |
| `angular` | `false` | Interpola como ángulo (wrap 0–360) — para rumbos. |
| `pad3` | `false` | Rellena el entero a 3 dígitos (`005`). |
| `thousands` | `false` | Separador de miles (`1,626`). |
| `signed` | `false` | Prefijo `+` en valores positivos (ascenso en V/S). |
| `dir_source` | `"Wind Direction (deg)"` | Columna de dirección del viento (solo `kind="wind"`). |
| `speed_source` | `"Wind Speed (kt)"` | Columna de velocidad del viento (solo `kind="wind"`). |

Si falta el dato en el CSV, la fila muestra `--`. El viento **no se calcula**: la
aviónica Garmin ya lo registra en `Wind Speed (kt)` / `Wind Direction (deg)`.

### Ejemplo completo

```toml
[[widget]]
type = "info_panel"
x = 1670
y = 1060
width = 230

# Paleta JOTE (blanco/gris/negro)
bg_color     = [0.0, 0.0, 0.0, 0.60]
border_color = [1.0, 1.0, 1.0, 0.35]
label_color  = [0.72, 0.72, 0.72, 1.0]
value_color  = "white"

rows = [
  { label = "GS",    source = "GPS Ground Speed (kt)",   unit = " KT" },
  { label = "ALT",   source = "Baro Altitude (ft)",      unit = " ft",  thousands = true },
  { label = "V/S",   source = "Vertical Speed (ft/min)", unit = " fpm", signed = true },
  { label = "TRACK", source = "GPS Ground Track (deg)",  unit = "°", angular = true, pad3 = true },
  { label = "WIND",  kind = "wind" },
]
```

## Ícono del avión

`assets/aircraft_icon.png` — vista superior JOTE, se auto-recorta al bounding-box
no-transparente para centrarse correctamente en la heading rose.
