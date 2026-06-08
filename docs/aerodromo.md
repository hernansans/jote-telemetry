# Aeródromo Alta Gracia, Córdoba — contexto operativo

- **Elevación oficial:** 1.748 ft MSL
- **Desnivel entre cabeceras de pista:** 48 ft
- **AGL:** se calcula sobre **Pressure Altitude**, no sobre altitud GPS ni MSL directa.
  Esto neutraliza las variaciones de QNH entre vuelos y permite comparar AGL de forma
  consistente a lo largo del programa de ensayos.

## Por qué importa para el análisis

- Cualquier cálculo de AGL real en el reporte debe restar la elevación del aeródromo
  (1.748 ft) de la Pressure Altitude registrada por el GDU 460, ajustando según la
  cabecera en uso (el desnivel de 48 ft afecta AGL en el despegue/aterrizaje según el sentido).
- No usar altitud GPS para AGL — el log puede traerla, pero no es la referencia válida
  para este análisis.
