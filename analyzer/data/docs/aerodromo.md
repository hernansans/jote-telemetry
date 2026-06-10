# Contexto del aeródromo

Referencia usada por el motor de análisis para calcular AGL y contextualizar el vuelo.

## Elevación

- **Elevación oficial:** 1.748 ft MSL.
- La **altura sobre pista** del análisis se calcula sobre **Pressure Altitude**
  (`Pressure Altitude (ft)` del log), no sobre altitud GPS ni sobre la columna
  `Height Above Ground (ft)` del G3X.

- **Importante:** `Pressure Altitude` está referida a la presión estándar (29.92"), **no al
  QNH del día**. Por eso en tierra NO marca la elevación oficial (1.748 ft): en un día de
  alta presión puede marcar, por ejemplo, ~1.520 ft. Restar la elevación oficial fija
  introduce un **error sistemático** igual a la diferencia presión-estándar/QNH de ese día
  (puede ser de cientos de pies).

- Por eso el análisis **detecta la referencia de pista de cada vuelo** desde los propios
  datos: toma la mediana de `Pressure Altitude` con el avión detenido en tierra
  (`GPS Ground Speed` ≈ 0) y la usa como cero:

  ```
  altura_sobre_pista (ft) = Pressure Altitude (ft) − referencia_de_pista_detectada
  ```

  Esto sí neutraliza la variación de QNH y da una altura repetible entre vuelos.
  (Ver `engine_analyzer/phases.py`.)

- A título comparativo el reporte también muestra `AGL (vs elev. oficial) = Pressure Altitude
  − 1.748`, que es el que aparece "corrido" por lo explicado arriba.

- La columna `Height Above Ground (ft)` del G3X (deriva de altitud GPS/terreno) se registra
  solo como control cruzado; no es la referencia del análisis.

## Pista

- **Desnivel entre cabeceras:** 48 ft. Según la cabecera en uso, la elevación efectiva del
  punto de despegue/toque varía dentro de ese rango. Para VLOF y carreras de despegue
  (PERF01) tener presente cuál cabecera se usó.

## Notas

- Estos valores son contexto operacional del campo donde se hacen los ensayos JOTE.
  Si se vuela desde otro aeródromo, actualizar este archivo antes de correr el análisis.
