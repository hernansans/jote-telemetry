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

**Resuelto — proxy operacional en vez de detectar la fase exacta:**
Hernán mismo señaló que "desde la prueba de magnetos" es difícil de delimitar con
precisión en la telemetría, y propuso un proxy simple y verificable: alertar cuando
RPM > 3000 (alta potencia) Y la temperatura de aceite sigue por debajo del rango
operativo normal (90°C / 194°F). Esto evita tener que detectar la fase exacta —
si el motor recibe alta potencia sin haber calentado, hay alerta; si nunca se cruza
ese umbral de RPM con temperatura baja, no la hay (calentamiento normal en rodaje).

**How to apply:** implementado como `regla_alta_potencia_sin_temp_operativa` en
`docs/limites.yaml` (bajo `motor.temp_aceite`) y evaluado en
`src/limits_engine._check_alta_potencia_sin_temp_operativa`. Es una regla compuesta
de dos columnas (RPM + temperatura), no un límite simple de una sola variable —
documentar cualquier regla similar (por fase de vuelo, por condición compuesta) con
el mismo patrón: umbrales explícitos + condición declarada en YAML + función dedicada
en el motor, citando que es "regla operacional definida por el constructor" cuando no
proviene directamente de un manual.
