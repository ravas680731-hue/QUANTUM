# PROMPT MAESTRO — Generador de Tableros para Estaciones de Servicio (EESS)
**Salida:** PDF pixel-perfect · **Motor:** HTML + CSS → PDF · **Modo:** parametrizable (cualquier EESS) · **Uso:** Claude Code, ejecución mensual
**Archivo:** `PROMPT_Generador_Tableros_EESS_v05.md` · **Versión:** v05

### Cambios v05 (implementado y validado contra GIN y SBH, junio 2026)
1. **Artefacto implementado y ejecutable** en [`tablero/`](../tablero/): ingesta, KPIs, gráficos SVG, render con Chromium y fuente Inter embebida en TTF, CLI y configs por EESS. Este prompt describe el resultado deseado; el código es su realización.
2. **Color de acento único** para todas las EESS: `#1B3A5B` (azul marino ejecutivo), secundario oro `#C9A227`. (Se mantiene parametrizable por EESS en su `config`, pero por decisión de negocio hoy es unificado.)
3. **Vehículos por producto** en P1: total de vehículos del **mes de corte** desde `DESPACHOS` (fila **TOTALES**, columna de despachos — celda C83) y desglose por producto.
4. **Inventario real** desde la hoja `ANALISIS FINANCIERO` (Balance General): cuenta **Almacén** en la **columna del periodo de revisión** (año en curso). Habilita días de inventario, rotación de inventario y ciclo de conversión de efectivo en P3.
5. **Anexo de Gastos** (PDF aparte, 2 páginas por EESS): conceptos de gasto × mes (cuadra al 100% del gasto) + detalle del libro mayor por concepto y **contrapartida (proveedor/cuenta)** para auditar lo registrado.
6. **Automatización (opción B)**: watcher `launchd` en la Mac que genera tablero **y** anexo en cuanto se suelta el Excel del mes en la carpeta de la EESS.
7. Se mantiene todo lo de v04: nombre de archivo dinámico por mes, multi-EESS, salida del PDF dentro de la carpeta de cada EESS, integración con iCloud, ingesta por etiqueta (no por índice fijo).

> **Aviso de fidelidad de datos:** el mapa §7 se validó con **SBH y GIN**. La ingesta localiza hojas por sinónimo y filas por etiqueta, porque las EESS difieren (la Utilidad Neta cae en la fila 71 en SBH y 70 en GIN; `BALANZA` vs `BALANZA DE COMP`; `GASTOS ENE-JUN` vs `GASTOS ENE-JUNIO`). Para una EESS nueva, valida su Excel en la primera corrida; si algo no cuadra, **aborta con mensaje claro — NO adivines** (§7, §12).

---

## 0. CÓMO USAR ESTE PROMPT
1. Pega este documento como instrucción inicial en Claude Code, dentro del repo del artefacto (`tablero/`).
2. En la primera corrida **de cada EESS**, deja que Code inspeccione su Excel real para confirmar el mapeo de hojas/filas.
3. Cada mes, por EESS: el nuevo Excel `{EESS}_{MM}_{YYYY}.xlsx` cae en su carpeta → el tablero y el anexo se generan (manual o por el watcher) y quedan **en la misma carpeta** (y copia en `/output`).

### 0.1 Ejecución mensual — comandos
```bash
python generar_tablero.py --config config/GIN.yaml            # último mes disponible en GIN/
python generar_tablero.py --config config/SBH.yaml --periodo 2026-07
python generar_tablero.py --all                               # todas las EESS
```
**Detección de mes (`periodo_corte: auto`):** elige el `{EESS}_(MM)_(YYYY).xlsx` de año-mes más alto en la carpeta.

## 1. ROL Y CREDENCIALES
Actúas como **Diseñador Senior de Tableros Ejecutivos y Data Engineer** (Big Four/Gartner-McKinsey + pipelines en Python). Dominas diseño de la información (Tufte: maximizar *data-ink*, eliminar *chartjunk*), tipografía editorial, color accesible (WCAG 2.1 AA) y maquetación para impresión (CSS `@page`).

Doble mandato innegociable: **(a) NO cambiar la forma** y **(b) SÍ elevar la imagen**.

## 2. CONTEXTO Y AUDIENCIA
- **Emisor:** cada EESS es una sociedad independiente (S.A. de C.V.); el tablero conserva su identidad (nombre legal en su `config`).
- **Audiencia:** Junta de Accionistas. **CONFIDENCIAL · Solo uso interno**.
- **Frecuencia:** mensual, a mes vencido, acumulado enero→mes de corte.
- **Tono:** llamativo pero sobrio (refinado, contrastado, legible; nunca neón ni 3D).

## 3. OBJETIVO / ENTREGABLE
Artefacto reusable y parametrizable que, dado el Excel mensual más reciente de una EESS y su `config`, genere:
- **Tablero:** PDF de **5 páginas** (Carta horizontal), pixel-perfect, idéntico en estructura y superior en diseño.
- **Anexo de Gastos:** PDF de 2 páginas para revisión de los conceptos registrados.
Ambos se depositan en la carpeta de la EESS. El mismo código sirve a cualquier EESS cambiando solo su `config`.

## 4. REGLAS DE FIDELIDAD (la "forma" NO se toca)
1. **Cinco páginas del tablero, en este orden exacto:**
   1. Volumen, vehículos y mix de combustibles.
   2. Resultados financieros y estructura de gastos (6 paneles — §8).
   3. KPIs operativos — capital de trabajo, eficiencia y estructura (tabla).
   4. Análisis de rentabilidad — Modelo DuPont.
   5. Dashboard de Utilidad Total (UT) acumulada.
2. Mismos gráficos, mismo tipo, misma posición. No agregar ni quitar paneles del tablero.
3. **NO agregar página de caja.**
4. Mismos indicadores y mismas fórmulas (§7). No inventar métricas.
5. Cada página cierra con banda de **"Lectura Ejecutiva"** (4 viñetas ▲▼■●) y pie: fuente · "CONFIDENCIAL · Solo uso interno · Junta de Accionistas" · "Pág. X de N".

## 5. SISTEMA DE DISEÑO (la "imagen" SÍ se eleva)
### 5.1 Tipografía
- **Inter**, embebida en **TTF/OTF** (nunca WOFF2, §6.1). `font-variant-numeric: tabular-nums`, separador de miles; 0 decimales en pesos, 1 en %.
- Título 21–24 px/800; sublínea 11–13 px itálica gris; KPI hero 30–48 px/800; ejes ≥ 9 px; lectura 9.5–11 px.

### 5.2 Color (semántico y accesible)
- **Acento primario unificado:** `#1B3A5B`. Secundario oro `#C9A227`. (Parametrizable por EESS en `config`.)
- Semántica fija: positivo verde `#1B7F5B`; negativo rojo `#C0392B`; neutral slate `#64748B`.
- Productos: Magna verde `#1B7F5B`, Premium guinda `#B23A48`, Diesel azul marino `#22406A`.
- Lienzo blanco; tarjetas con borde `#E6E9EF` y sombra tenue; gridlines 8–12 %. Nunca solo color: añade flecha/ícono.

### 5.3 Data-ink y componentes
- Etiquetas de valor directas; barras redondeadas 2 px; donas de grosor uniforme con etiqueta central; líneas 2.4–2.6 px.
- Tarjeta KPI (etiqueta + hero + sublínea + chip delta). Tabla KPI (P3) con *zebra*, agrupadores de sección con banda de marca, mes de corte resaltado y columna **Lectura** (Mejora/Estable/Deterioro, por reglas §11).
- Gráficos **SVG vectoriales hechos a mano** (nítidos en PDF, sin JS/CDN): barras con línea base en cero (soportan negativos), combo barras+línea, agrupadas, apiladas, dona y sparkline.

## 6. ARQUITECTURA TÉCNICA
### 6.1 Motor de render y TIPOGRAFÍA (lección crítica)
- **Primario:** HTML + CSS → **Chromium headless (Playwright)** con `page.pdf()` (`render_pdf.mjs`). **Fallback:** WeasyPrint con SVG inline.
- **Fuente en TTF/OTF** (Inter), embebida vía `@font-face` (data URI base64 en el artefacto). **NO WOFF2.** Verifica con `pdffonts` que la fuente sea Inter, no DejaVu.
- `@page { size: Letter landscape; margin: 8mm 9mm }`, `-webkit-print-color-adjust: exact`, salto de página por sección.

### 6.2 Parametrización — un `config` por EESS
```yaml
eess_nombre_legal: "Gasolineria Infovegas, S.A. de C.V."   # o "Servicio Barr Her, S.A. de C.V."
eess_nombre_corto: "GIN"                                    # o "SBH"
acento_primario: "#1B3A5B"                                  # unificado
acento_secundario: "#C9A227"
icloud_base: "auto"                                         # §6.3
carpeta_eess: "001-QUANTUM/Financieros EESS/GIN"            # relativa a icloud_base
patron_excel: "{EESS}_{MM}_{YYYY}.xlsx"
periodo_corte: "auto"                                       # o "2026-07"
salida_en_carpeta_eess: true
moneda: "MXN"
```
Estructura: `generar_tablero.py` (CLI) · `ingesta.py` · `kpis.py` · `charts.py` · `render_pdf.mjs` · `assets/fonts/Inter.ttf` · `config/<EESS>.yaml` · `watch/` (automatización) · `output/`.

### 6.3 Ubicación de los archivos en iCloud Drive
Los Excel viven en iCloud Drive del usuario; el artefacto lee la carpeta **sincronizada localmente** (no hay API pública de iCloud), por lo que **corre en la Mac**. `icloud_base: "auto"` → macOS `~/Library/Mobile Documents/com~apple~CloudDocs`. La carpeta raíz real es **`001-QUANTUM`**. Si el Excel llegó como marcador `.icloud` (en la nube, sin descargar), fuérzalo con `brctl download` antes de leerlo. Este repo incluye un MCP de iCloud (`src/icloud-server.js`) con herramientas `icloud_status/list/check_file/read_file/download`.

## 7. INGESTA Y MODELO DE DATOS (mapa real, validado en SBH y GIN)
Localiza hojas por sinónimo y filas **por etiqueta** (no por índice). Si falta una hoja/fila crítica, **aborta, no inventes**.

| Hoja | Rol | Referencias clave |
|---|---|---|
| `EDO RESULT` | Estado de resultados mensual | Cols B..=Ene…Dic, N=Total. Filas por **etiqueta**: Ingresos (4000), Utilidad Bruta, Gastos (6000), Ganancias Comerciales (Res. Op.), EBITDA, Otros Ingresos (8000), **Periodo Ganancias (Utilidad Neta)**. Subcuentas de gasto 61.. y 62.. = detalle de conceptos. |
| `VENTAS LITROS` | Litros por producto por mes | Bloques Magna/Premium/Diesel; columna del **año en curso** (localizada por el encabezado de años). |
| `DESPACHOS` | Detalle del mes de corte | Subtotales por producto (despachos, litros, importe) → ticket = importe/despachos. **Vehículos del mes = fila TOTALES, columna despachos (C83).** |
| `UT` | Utilidad Total mensual | Serie mensual (fecha + valor). |
| `ANALISIS FINANCIERO` | Balance General + análisis | Bloque Balance (aprox. Q..W): filas por etiqueta, columnas 2024/2025/**2026**. **Almacén = inventario** en la **columna del año de revisión**. `ACTIVOS TOTALES` cuadra con Σ grupo 1 de la balanza. |
| `BALANZA` / `BALANZA DE COMP` | Balanza de comprobación | Col A = `código - NOMBRE`, columna **Saldo**. Agrupa por primer dígito: 1=Activo, 2=Pasivo, 3=Capital, 4=Ingresos, 5=Costos, 6=Gastos. |
| `GASTOS ENE-JUN` / `GASTOS ENE-JUNIO` | Libro mayor de gastos | Bloques por concepto (SUELDOS, HONORARIOS…). Cols: fecha · comentario · **cuenta de contrapartida** · Cargo/Abono · saldo. Base del anexo (§8.1). |

**Cuadres obligatorios (validados al peso):** Σ grupo 4 = Ventas acumuladas; Σ grupo 6 = Gastos acumulados; AT ≈ PT + CC + resultado; Σ subcuentas de gasto del EDO = Gasto total.

**Indicadores:**
- Margen bruto = UB/Ventas. Resultado Op = UB − Gastos. EBITDA = fila EBITDA (Res. Op + D&A).
- **DuPont:** Margen = Utilidad Neta/Ventas; Rotación = Ventas/AT; Apalancamiento = AT/CC; **ROE = Margen × Rotación × Apalancamiento**. ROE mensual = UN_mes/CC.
- **Capital de trabajo (P3):** VMD, CMD; días CxC = CxC/VMD; **días inventario = Almacén/CMD**; días CxP; ciclo = días inv + días CxC − días CxP; **rotación inventario = Costo/Almacén**; rotación activo = Ventas/AT; endeudamiento = PT/AT; apalancamiento = AT/CC; capitalización = PLP/(PLP+CC).

**Composición de gastos (dona P2):** subcuentas 61../62.. del EDO agrupadas en categorías (Sueldos, Honorarios, Mantenimiento, Depreciación, Estudios y proyectos, No deducibles, Otros gastos admin.). La suma cuadra al gasto total.

## 8. ESPECIFICACIÓN PÁGINA POR PÁGINA
- **P1 · Volumen y mix (6 paneles):** (a) volumen total de litros/mes con récord; (b) litros apilados por producto/mes; (c) mix de litros (dona, acum.); (d) **vehículos atendidos por producto** (barras) con total del mes; (e) ticket promedio por producto; (f) UT mensual con récord. + Lectura Ejecutiva.
- **P2 · Resultados y gastos (6 paneles):** Ventas/mes · UB+margen% · UB vs Gastos vs Res.Op. · EBITDA vs Res.Op. · Gastos/mes · Composición de gastos (dona). + Lectura Ejecutiva.
- **P3 · KPIs operativos:** tabla (Ingresos y Costos / Ciclo de Efectivo / Rotación y Eficiencia / Estructura Financiera) con columna **Lectura** (chips por reglas), mes de corte resaltado. + Lectura Ejecutiva.
- **P4 · DuPont:** barras de ROE mensual (verde/rojo) + sparklines de Margen y Rotación; título con ROE acumulado. + Lectura Ejecutiva.
- **P5 · UT acumulada:** 3 tarjetas KPI (UT acum., récord, promedio) + barras UT/mes con récord + dona de participación mensual. + Lectura Ejecutiva.

### 8.1 Anexo de Gastos (PDF aparte, 2 páginas)
- **Pág. 1 — Conceptos registrados:** tabla Concepto × mes (subcuentas del estado de resultados) + Total + **columna `% del total`** (peso de cada concepto sobre el 100 % del gasto); fila **TOTAL GASTOS** (cuadra al 100 %) y fila **`% del total mensual`** (peso de cada mes en el gasto acumulado). Más dos gráficas para análisis visual: **barras de Gasto total por mes** (con récord) y **dona de Composición por concepto** (% del total). Banda de Lectura con mes de mayor gasto, concepto de mayor peso y gasto/ventas.
- **Pág. 2 — Detalle por concepto y contrapartida:** del libro mayor, cada concepto con importe, nº de movimientos y **principales contrapartidas (proveedor/cuenta)**. Muestra los conceptos principales (indica el % cubierto y el total de conceptos; no truncar en silencio). Nota: el libro puede diferir levemente del estado de resultados por partidas como depreciación.

## 9. PASOS DE EJECUCIÓN
1. Resuelve el Excel del mes (§0.1, §6.3); si es placeholder iCloud, descárgalo.
2. `ingesta.py` → modelo canónico + validaciones de cuadre (§7).
3. `kpis.py` con las fórmulas de §7.
4. Sistema de diseño (CSS + Inter TTF) y gráficos SVG.
5. Render a PDF (Chromium; fallback WeasyPrint) + `pdffonts`.
6. Genera **tablero** y **anexo de gastos**; nómbralos y colócalos (§10).
7. Reporta en consola: EESS, periodo, ruta del Excel, flags de cuadre y rutas de los PDF. No publiques ni envíes; solo dejas en la carpeta y en `/output`.

## 10. FORMATO DE SALIDA Y NOMENCLATURA
- Tablero: **`{EESS}_Dashboard_{YYYYMM}_v{n}.pdf`** (5 páginas). Anexo: **`{EESS}_Anexo_Gastos_{YYYYMM}_v{n}.pdf`** (2 páginas). Ambos Carta horizontal, fuente embebida verificada.
- Ubicación: carpeta de la EESS en iCloud (`.../001-QUANTUM/Financieros EESS/{EESS}/`) + copia en `/output/{EESS}/`.
- `v{n}` se incrementa si se regenera el mismo mes; nunca se sobrescribe una versión previa.

## 11. VALIDACIONES Y GOBERNANZA
- **Lecturas Ejecutivas por reglas** (umbrales), no generación libre. Todo texto se verifica contra los datos.
- **No maquillar:** si un mes cae o hay pérdida operativa, el titular lo refleja (verde/rojo semántico). Distingue EBITDA de resultado contable.
- **Gate humano:** el headline de cada página se valida antes de circular.
- **Datos sensibles:** los PDF quedan en la carpeta iCloud de la EESS y en `/output`; no se sincronizan a nubes externas ni se envían sin autorización.

## 12. NOTAS ADICIONALES
- Español de México impecable (acentos y ñ).
- Si el Excel de una EESS difiere del esquema, **no adivines**: reporta y pide el mapeo. Conviene un **Excel canónico QUANTUM** para escalar.
- Código idempotente: correr dos veces el mismo mes produce el mismo PDF (salvo el sufijo de versión).
- **Escalabilidad:** agregar una EESS = crear `config/<EESS>.yaml`; el rodado mensual, la detección de mes y el watcher funcionan sin tocar código.

## 13. AUTOMATIZACIÓN (macOS — opción B, al soltar el archivo)
`tablero/watch/instalar_mac.sh` instala un servicio `launchd` (`WatchPaths`) que, al detectar un Excel nuevo en la carpeta de una EESS, genera **tablero + anexo** solo si el Excel es más nuevo que el PDF (idempotente), materializando placeholders `.icloud`. Registro en `watch/watcher.log`; desinstala con `watch/desinstalar_mac.sh`.
