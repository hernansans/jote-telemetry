# Memoria del proyecto JOTE Telemetry

Índice de memorias. Cada línea apunta a un archivo con el detalle.

- [Convenciones de límites](convenciones-limites.md) — cómo se documentan límites en docs/limites.yaml
- [Límites extraídos de los manuales](limites-extraidos.md) — qué ya está completo en limites.yaml y qué queda pendiente/abierto
- [Fases de vuelo y temperaturas](fases-de-vuelo.md) — por qué no se evalúa temp. mínima de operación durante el rodaje/calentamiento
- [Presión de aceite es mandatoria](presion-aceite-mandatoria.md) — distinguir "mandatorio pero condicional" de "sin valor publicado" al listar pendientes
- [Presión de aceite — análisis correcto](presion-aceite-analisis.md) — cómo filtrar fases (excluir RPM<1500), valores normales en crucero (~45 PSI), por qué los negativos al arranque son ruido de sensor
- [Overlay HUD](overlay-hud.md) — diseño del módulo de video overlay, widgets custom, bugs resueltos, comandos de render
- [Codec del overlay (Resolve)](overlay-codec-resolve.md) — editar en DaVinci Resolve ⇒ ProRes 4444; qtrle no lo importa (es opción opt-in, no default)
- [Integración de analyzer/](analyzer-integracion.md) — motor v2 (jote-analyzer): fases de vuelo, límites condicionales, reportes LLM, qué se mantiene de src/ legado
