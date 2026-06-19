# Overlay HUD — decisiones de diseño

## Qué es

Fork de [flighthud](https://github.com/jfromaniello/flighthud) customizado para el JOTE LV-X7030.
Genera un archivo `.mov` transparente (ProRes 4444 alpha, `yuva444p10le`) que se compone
sobre el video del vuelo en el editor. Mismo CSV del GDU 460 que usa `src/` para el análisis.

## Templates

### `jote_cockpit`
PFD completo para tomas de cabina:
- Artificial horizon (style=pfd, 1180×700)
- Speed tape IAS con bandas verde/amarillo/rojo
- Altímetro vertical tape
- VSI tape
- Heading rose con ícono JOTE (zoom=0.32)
- OAT readout
- EIS panel completo

### `jote_EIS`
Para tomas exteriores donde no se ve la cabina:
- EIS panel (MAP, RPM, FUEL, OIL, EGT×4, CHT, AMPS, FLAP, VOLTS)
- IAS circular (dial_gauge, r=69, alineado con MAP)
- VSI circular (dial_gauge, r=69, alineado con RPM)

### `jote_info`
Panel de telemetría simple arriba a la derecha (`info_panel`): GS, ALT (baro),
V/S, TRACK, WIND. Réplica del overlay "simple" de joseflys /replay.

## Widgets custom (`overlay/src/flighthud/widgets/eis.py`)

### `eis_panel`
Panel EIS compacto estilo Garmin G3X. Layout en tres bandas:
- Superior: diales MAP y RPM (r=69, circulares con bandas de color en arco)
- Media: barras horizontales FUEL L/H, OIL PSI, OIL °C — sin fondo (transparente sobre video)
- Inferior: EGT×4 (barras verticales), CHT, AMPS, FLAP, VOLTS — con fondo semitransparente

### `dial_gauge`
Dial circular standalone en el mismo estilo que MAP/RPM. Configurable:
- `vmin`, `vmax` — rango
- `bands` — lista de `[v0, v1, color]`
- `start`, `sweep` — ángulo inicial y barrido (default: 220°/280°, estilo aeronáutico)
- `unit`, `decimals` — formato del valor digital

## Widget `info_panel` (`overlay/src/flighthud/widgets/info_panel.py`)

Réplica del HUD "simple" de joseflys /replay: panel redondeado semitransparente
con filas etiqueta-chica-atenuada sobre valor-grande-blanco. Misma paleta que el
HUD web de joseflys (Tailwind slate): fondo slate-900 @ 0.8, borde slate-600,
etiquetas slate-400, valores blancos.

- Anclado por su **borde superior**: `x`,`y` = esquina superior-izquierda; crece
  hacia abajo (a diferencia de los demás widgets que usan esquina inferior-izq).
- Filas configurables via `rows` (inline tables TOML); default = GS / ALT (baro) /
  V/S / TRACK / WIND. Flags por fila: `decimals`, `unit`, `angular` (interp de
  ángulo), `pad3` (rumbo a 3 dígitos), `thousands`, `signed` (prefijo + en V/S),
  `transform`. `kind="wind"` combina `Wind Direction (deg)` + `Wind Speed (kt)`.
- El viento **no se calcula**: la aviónica Garmin ya lo registra. Hubo que sumar
  `Wind Speed (kt)` y `Wind Direction (deg)` a `NUMERIC_COLUMNS` en `data.py`
  (no estaban). Si falta el dato, la fila muestra `--`.

## Bugs resueltos

### Speed tape bands bleeding
**Síntoma**: las bandas de color del speed tape se "estiraban hacia arriba" fuera del marco.
**Fix definitivo** en `pfd.py` → `VerticalTape.create_dynamic()`:
```python
_clip_path = MplPath.unit_rectangle()
_clip_tf   = Affine2D().scale(w, h).translate(x, y) + ax.transData
artist.set_clip_path(_clip_path, _clip_tf)   # forma de dos argumentos
```
La forma de un argumento (`set_clip_path(Rectangle(...))`) no funciona con patches
no-añadidos al axes en el backend Agg con multiprocessing.

### MemoryError en render
**Causa**: 16 workers × buffers matplotlib Agg × page file lleno en C: (~10 GB libres).
**Fix**: `-j 6` en el comando de render. Con 6 workers funciona estable (~120 MB RAM/worker).

### IndexError al final del render (clip más allá del log)
**Síntoma**: `IndexError: single positional indexer is out-of-bounds` en
`FrameData.__init__` (`df.iloc[idx0]`) hacia el final del render.
**Causa**: `FrameData` topeaba `idx0` solo por abajo (`max(0, idx0)`), no por arriba.
Cuando `offset + duración` excede el largo grabado del log, `t_log ≥ len(df)` e
`idx0` se sale de rango. Bug pre-existente, no lo introdujo `--render-fps`.
**Fix** (`data.py`): topear ambos índices al último válido
(`idx = min(max(0, idx), len(df)-1)`); los frames pasados el final se congelan en
la última muestra. **Ojo de uso**: el offset default es 331 s — para el vuelo real,
fijar `--offset` y `--duration` dentro del log para no rendear una cola congelada.

## Render rápido: `--render-fps` (desacople render rate / output fps)

El HUD cambia lento ⇒ no hace falta un render por cada frame de salida. `--render-fps N`
renderiza N frames únicos/seg (4–6 alcanza) y ffmpeg los duplica hasta `--fps`
(`-framerate render_fps -i ... -r output_fps`). Default = `--fps` (1:1, sin cambios).
Reduce los renders ~5–6×. Misma técnica que joseflys (`inputFps`/OverlayMotion).
Para salida a carpeta PNG, los frames quedan a `render_fps` y el CLI imprime el
comando ffmpeg con el `-framerate` correcto. Implementado en `pipeline.py`
(`generate`/`render_video`/`_ffmpeg_encode_cmd`) + flag en `cli.py`.

## Render

```bat
# Render completo (en A:, no en C:)
uv run flighthud log.csv -o A:\frames --offset 0 --duration 1250 -t jote_cockpit -j 6

# Encode ProRes 4444 alpha
ffmpeg -y -framerate 30 -i A:\frames\frame_%06d.png ^
  -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 overlay.mov
```

Duración render completo (37,500 frames): ~1.5–2 horas. Archivo final: ~19–20 GB.
