# Acta de cierre de prueba — Estación SBH

**Fecha/hora del acta:** 2026-07-15 12:37 CST (America/Mexico_City)
**Estación:** SBH · Servicio Barr Her, S.A. de C.V.
**Permiso CNE:** `PL/6812/EXP/ES/2015` (normalizado `PL-6812-EXP-ES-2015`)
**Semana operativa vigente:** 2026-29 (14–20 jul 2026, Mar→Lun)

---

## 1. Resultado de las 5 validaciones (post-migración)

Ejecutadas desde la nueva estructura `estaciones/PL-6812-EXP-ES-2015/`:

| # | Validación | Resultado |
|---|---|---|
| 1 | Backtest walk-forward | ✅ PASA (ver tabla) |
| 2 | Calendario 2026/2027 (Pascua 2026=5-abr, 2027=28-mar) | ✅ PASA |
| 3 | Congelamiento de deriva (6 días sin recepción → 1.0) | ✅ PASA |
| 4 | Idempotencia (doble corrida = salidas idénticas) | ✅ PASA |
| 5 | Assert de régimen (PREMIUM/DIESEL ≥ 2026-01-01) | ✅ PASA |

**Backtest (validación 1) por producto:**

| Producto | MAPE | Umbral | Estado |
|---|---|---|---|
| MAGNA | 7.28 % | ≤ 9 % | ✅ PASA |
| PREMIUM | 15.33 % | ≤ 16 % | ✅ PASA |
| DIESEL | 18.46 % | ≤ 19 % | ✅ PASA |

---

## 2. Cambio de programación de la corrida automática

| Campo | Antes | Después |
|---|---|---|
| Día | Lunes | **Martes** |
| Hora | 07:00 | **10:00** |
| `Weekday` (launchd) | 1 | **2** |
| Ventana pronosticada | Mar→Lun | **Mar→Lun** (sin cambio) |
| Corte de datos | hasta lunes | **hasta domingo** (lunes = hueco imputado) |
| Vigente desde | — | **2026-07-15** |

**Motivo:** el control volumétrico entrega con 24 h de retraso (los datos del
domingo están disponibles el lunes). El operador carga los CSV el **lunes antes de
las 6:00 PM** con datos hasta el domingo; la corrida ocurre el **martes 10:00**.
Registro trazable en `datos/estado/cambios_programacion.csv` y en la columna
`inicio_operativo` de la bitácora.

**Verificación de horizonte (lags sin corte fijo en lunes):**

| Escenario | Origen (último dato) | Inicio ventana | Hueco | Lags nulas |
|---|---|---|---|---|
| Datos hasta lunes | Lun 2026-07-13 | Mar 2026-07-14 | 0 | 0 |
| Datos hasta domingo (simulacro) | Dom 2026-07-12 | Mar 2026-07-14 | 1 (lun, imputado) | 0 |

---

## 3. LaunchAgent — confirmación de carga y próxima ejecución

`launchctl list`:

```
-	0	com.quantum.pronostico
```

(estado `LastExitStatus = 0`, cargado y en espera). Horario efectivo del job
(`launchctl print`):

```
state = not running
"Weekday" => 2      (martes)
"Hour"    => 10
"Minute"  => 0
```

**Próxima ejecución programada:** martes **2026-07-21 10:00** CST
(el 2026-07-15 es miércoles; el siguiente martes es el 21).

---

## 4. Estado de la copia a Google Drive

**Copia realizada:** ✅ 2026-07-15 12:37 CST
**Destino (estructura por estación):**
`~/Library/CloudStorage/GoogleDrive-…/Mi unidad/QUANTUM/norte-b/pronostico-sbh-salidas/PL-6812-EXP-ES-2015/2026-29/`

| Archivo | Tamaño |
|---|---|
| dashboard_semanal.html | 22,538 B |
| pedido_sugerido.md | 957 B |
| pronostico_semana.csv | 935 B |

Solo se replica `salidas/<PERMISO_NORM>/` — **nunca** `datos/entrada/` ni
`datos/estado/` (datos sensibles, exposición mínima).

---

## 5. Veredicto operativo de la semana (2026-29)

> **Esta semana pide 4 pipas de Magna, 1 pipa de Premium y 1 pipa de Diésel.**

---

_Acta generada automáticamente. Datos de SBH — uso interno · QUANTUM Insight._
_Sistema: pronóstico semanal EESS, arquitectura multi-estación por permiso CNE._
