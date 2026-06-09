---
name: presion-aceite-mandatoria
description: La presión de aceite es un límite mandatorio del Rotax 912 ULS, no un dato informativo
metadata:
  type: feedback
---

La presión de aceite **es un límite mandatorio**, citado explícitamente en el manual
del motor con procedimientos de emergencia dedicados ('Oil pressure below minimum'
en tierra y en vuelo, 'Oil pressure above permitted range at low ambient temperatures' —
Rotax OM 912 Ed.4/Rev.1, Sec. 3.4/3.4.1/3.4.2, pág. 3-4 a 3-5).

**Why:** Hernán corrigió la primera versión del análisis: "la presión de aceite sí es
mandataria, leé el manual pdf de Rotax y ahí lo dice". El error no estaba en
`docs/limites.yaml` (ya tenía los valores y la cita correcta) sino en cómo describí el
resultado: agrupé "presión de aceite según RPM" junto con la curva MAP bajo
"pendientes (límites condicionales)" sin aclarar que unos son mandatorios-pero-complejos
y otros son genuinamente informativos — esa ambigüedad podía leerse como "no es
mandatorio".

**How to apply:** distinguir siempre dos motivos distintos para que algo quede en
"pendientes" del motor de comparación ([[convenciones-limites]], [[limites-extraidos]]):
1. **Mandatorio pero condicional** (presión de aceite según RPM, RPM transitorio con
   tolerancia de tiempo, IAS según fase de vuelo): requiere lógica específica, pero
   SÍ debe terminar generando alertas de "fuera de límite".
2. **Genuinamente sin valor numérico publicado** (alternador, MAP sin curva, MISCOMP
   de aviónica): se trata como monitoreo/conteo, no como excursión de límite.
Nunca presentar ambos grupos como si fueran lo mismo — el primero es trabajo pendiente
de implementación, el segundo es una limitación real de la documentación fuente.
`docs/limites.yaml` ya marca `es_mandatorio: true` en `motor.presion_aceite` para que
quede explícito en el dato, no solo en la prosa.
