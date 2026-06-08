---
name: fases-de-vuelo
description: Por qué los límites de temperatura de operación no se evalúan desde el arranque del motor
metadata:
  type: project
---

Las temperaturas de operación del motor (aceite, refrigerante) **no deben analizarse
desde el encendido**. Durante la puesta en marcha y el rodaje el motor está calentando
de forma normal y gradual — es esperable que la temperatura esté por debajo del rango
de operación normal en ese tramo.

Lo relevante de la temperatura mínima de operación (50°C / 122°F de aceite, según
[[limites-extraidos]]) es que debe alcanzarse **antes de aplicar alta potencia**
(prueba de magnetos en adelante, incluyendo el despegue) — no que deba mantenerse
desde el arranque.

**Why:** Hernán (constructor y piloto de pruebas) señaló que es un error común analizar
la temperatura de operación incluyendo el rodaje: "uno pone en marcha y mientras va
calentando, se va moviendo por el rodaje, lo importante de la temperatura de operación
es desde la prueba de magnetos en adelante". Evaluar el mínimo como límite continuo
desde el arranque genera falsos positivos sistemáticos en cada vuelo.

**How to apply:** en `docs/limites.yaml` y en el motor de comparación
([[convenciones-limites]]), el mínimo de temperatura de aceite/refrigerante se trata
como una condición a verificar desde la prueba de magnetos en adelante (gate previo a
alta potencia), no como un mínimo absoluto de todo el log. Falta definir cómo detectar
ese punto en la telemetría (candidato: primer ascenso sostenido de RPM por encima del
ralentí hacia el rango de prueba de magnetos, ~1700-1800 RPM según Manual de Ensayos
Sec.5.3) — quedará resuelto cuando se implemente la lógica de fases de vuelo en el
motor de comparación.
