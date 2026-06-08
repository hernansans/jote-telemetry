---
name: convenciones-limites
description: Cómo se documentan los límites mandatorios en docs/limites.yaml
metadata:
  type: project
---

Todo límite en `docs/limites.yaml` debe citar manual + edición/revisión + página o sección
en el campo `fuente`. No se aceptan límites sin cita verificable.

**Why:** los reportes se llevan al taller como evidencia técnica — si un límite no se puede
rastrear al manual y página exacta, pierde valor como respaldo documental.

**How to apply:** al completar o corregir un valor en `limites.yaml`, completar `fuente`
en el mismo cambio. Si headear un PR que toca límites, verificar que cada valor nuevo
tenga su cita antes de aprobar.
