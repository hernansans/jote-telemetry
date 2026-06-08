---
name: limites-extraidos
description: Estado de extracción de límites desde los manuales hacia docs/limites.yaml
metadata:
  type: project
---

`docs/limites.yaml` ya tiene valores reales (no placeholders) para: RPM, temperaturas y
presión de aceite, temperatura de refrigerante, EGT, presión de combustible (Rotax OM 912
Ed.4/Rev.1, Sec. 2.2, pág. 2-5 a 2-7), e IAS/VNE/VNO/VA/VFE/VS/VSO (Manual JOTE rev.1 Sec.2.2,
pág. 11). VLOF documentado como procedimiento de determinación, no como valor fijo
(Manual de Ensayos en Vuelo JOTE v3, Sec. 8.4/9.2).

Quedan pendientes/abiertos:
- **MAP**: el manual del motor no trae una curva MAP-vs-RPM extraíble como tabla simple;
  falta localizarla o decidir si se compara solo cualitativamente.
- **Alternador (voltaje/amperaje)**: el Manual JOTE solo pide "monitorear", no publica
  límites numéricos — se registra para tendencias, no para detección de fuera-de-límite.
- **HDG MISCOMP / diferencia altimétrica G5 vs G3X**: el G3X Touch Pilot's Guide describe
  el mecanismo de alerta CAS 'MISCOMP' pero el umbral numérico se define en configuración
  de instalación (no es un valor publicado único). El análisis debe tratar esto como
  "contar ocurrencias del mensaje CAS", no como cruce de un límite numérico.
- **Canal del G5 en el log**: el CSV exportado es del PFD1 (G3X); no es evidente que
  traiga un canal de altitud del G5 standby — confirmar con un log real o preguntar al
  taller/instalador.

**Why:** evita que una futura sesión vuelva a abrir los PDFs completos para encontrar
estos mismos huecos — son límites que genuinamente no están publicados como valores únicos,
no datos que falte buscar mejor.

**How to apply:** al construir el motor de comparación ([[convenciones-limites]]), tratar
estos cuatro casos como "monitoreo/conteo" en vez de "comparación contra límite numérico".
