# Codec del overlay — DaVinci Resolve

El overlay de video JOTE se compone/edita en **DaVinci Resolve**. Por eso el
módulo `overlay/` exporta en **ProRes 4444 alpha** (`.mov`, `prores_ks
-profile 4444 -pix_fmt yuva444p10le`), que es lo que el pipeline ya hace.

## No usar qtrle como destino para Resolve

Aunque `qtrle` (QuickTime Animation / RLE) lleva alpha y es **mucho más rápido de
encodear** y genera archivos chicos para overlays planos, **DaVinci Resolve no lo
importa de forma confiable**: por un cambio en una librería de terceros el codec
Animation quedó sin soporte; en varias versiones los `.mov` Animation se leen
incluso como **archivos de audio**. Es limitación de larga data (cambios de
QuickTime en macOS).

Codecs con alpha que Resolve **sí** soporta para importar: ProRes 4444 / 4444 XQ,
DNxHR 444, y secuencias TIFF / OpenEXR / PNG.

Para iterar rápido sin pasar por Resolve, usar la **secuencia PNG** (`-o carpeta/`)
e importarla como image sequence. Reservar ProRes 4444 para el master de Resolve.

## Estado en el pipeline

`overlay/` tiene un flag `--codec {prores4444|qtrle|vp9}` (`pipeline.py` → dict
`CODECS`; `cli.py`). El default sigue siendo **por extensión** (.mov ⇒ prores4444,
.webm ⇒ vp9), así que el comportamiento previo no cambió. qtrle quedó como **opt-in**
(`--codec qtrle`, solo `.mov`), no default — por la limitación de Resolve.

El experimento de qtrle (donde es el codec default) está en
`~/Projects/oss/joseflys-overlay-generator` (`lib/ffmpeg.js`), pensado para
destinos no-Resolve (web / FCP / Premiere en Mac).

**Why:** En esta sesión sugerí qtrle por velocidad sin chequear el editor destino;
el dato del NLE es el que define el codec.
**How to apply:** Ante "¿qué formato/codec para el overlay?", responder ProRes 4444
mientras el destino sea Resolve; ofrecer qtrle/PNG solo para destinos no-Resolve.

Relacionado: [[overlay-hud]]
