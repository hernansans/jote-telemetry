# Presión de aceite — cómo analizarla correctamente

## El problema con el análisis directo

Si se evalúa la columna `Oil Press (PSI)` sobre todo el log sin filtrar fases,
aparecen valores de **−3 PSI** y cercanos a cero que disparan falsas alarmas.

**Causa**: al arranque en frío el sensor reporta ruido durante ~17 segundos antes
de que el motor gire lo suficiente para generar presión real. No es una falla de presión.

## Regla para el motor de comparación

**Excluir siempre RPM < 1500** del análisis de presión de aceite.
La presión solo es significativa cuando el motor está en RPM mínimas de operación.

```
# Fases para segmentar el análisis
tierra    : RPM < 1500                        → ignorar (arranque, sensor sin señal)
rodaje    : 1500 ≤ RPM < 3000 AND IAS < 20kt  → informativo
despegue  : RPM ≥ 3000 AND IAS < 40kt         → evaluar
vuelo     : RPM ≥ 3000 AND IAS ≥ 40kt         → evaluar con límites completos
```

## Valores observados en vuelo (log 20260605)

| Fase | Min | Max | Media | p50 |
|------|-----|-----|-------|-----|
| Rodaje | 35 | 60 | 46.1 | 44 PSI |
| Despegue/ascenso | 35 | 63 | 46.5 | 46 PSI |
| Vuelo establecido | 40 | 55 | 45.1 | 45 PSI |

**Cero segundos fuera del rango normal (29–72.5 PSI) en vuelo.**

## ¿45 PSI es baja?

No. Para el Rotax 912 ULS en crucero es completamente normal:

- Rango normal >3500 RPM según manual: **29–72.5 PSI** (2.0–5.0 bar)
- 45 PSI = **3.1 bar** → zona verde, tercio inferior del rango pero bien por encima del mínimo
- Patrón esperado: presión alta al arranque (~54 PSI con aceite frío/viscoso),
  baja al calentarse y se estabiliza en **42–47 PSI** en crucero → comportamiento normal
- La estabilidad es la señal clave: spread p5-p95 de solo 6 PSI durante todo el vuelo
  indica motor en buen estado sin variaciones de presión

**Referencia**: Rotax OM 912 Ed.4/Rev.1, Sec. 2.2, pág. 2-5
(valores originales en bar: normal 2.0–5.0 bar >3500 RPM, mínimo 0.8 bar <3500 RPM)

## TODO para el motor de comparación

Implementar evaluación condicional por RPM:
- Si RPM ≤ 3500: alertar si P_aceite < 11.6 PSI
- Si RPM > 3500: alertar si P_aceite < 29.0 PSI o > 72.5 PSI
- Excluir filas con RPM < 1500 (arranque)
