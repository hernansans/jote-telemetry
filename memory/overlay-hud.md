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

## Render

```bat
# Render completo (en A:, no en C:)
uv run flighthud log.csv -o A:\frames --offset 0 --duration 1250 -t jote_cockpit -j 6

# Encode ProRes 4444 alpha
ffmpeg -y -framerate 30 -i A:\frames\frame_%06d.png ^
  -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 overlay.mov
```

Duración render completo (37,500 frames): ~1.5–2 horas. Archivo final: ~19–20 GB.
