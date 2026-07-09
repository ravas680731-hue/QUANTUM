# PROMPT MAESTRO — Generador de Tableros para Estaciones de Servicio (EESS)
**Salida:** PDF pixel-perfect · **Motor:** HTML + CSS → PDF · **Modo:** parametrizable (cualquier EESS) · **Uso:** Claude Code, ejecución mensual
**Archivo:** `PROMPT_Generador_Tableros_EESS_v04.md` · **Versión:** v04

### Cambios v04 (multi-EESS + rodado mensual + salida en carpeta iCloud)
1. **Nombre de archivo dinámico por mes.** El Excel se sube a mes vencido con el patrón `{EESS}_{MM}_{YYYY}.xlsx` (`GIN_06_2026.xlsx`, luego `GIN_07_2026.xlsx`, `SBH_07_2026.xlsx`, etc.). El artefacto **detecta automáticamente el último mes disponible** en la carpeta de cada EESS; no hay que editar código cada mes.
2. **Varias EESS con la misma estructura de carpetas.** Cada EESS tiene su carpeta propia bajo `Financieros EESS/` (hoy `GIN/` y `SBH/`); el Excel del mes y el PDF resultante **conviven en esa misma carpeta**.
3. **El PDF se deja en la carpeta de la EESS**, no solo en `/output`: `.../Financieros EESS/GIN/GIN_Dashboard_202606_v01.pdf` y `.../Financieros EESS/SBH/SBH_Dashboard_202606_v01.pdf`. Se conserva copia en `/output` para versionado local.
4. **Ruta base de iCloud parametrizable** (`icloud_base`), porque los archivos viven en iCloud Drive del usuario. En una Mac se leen directo del disco sincronizado; ver §6.3.
5. Se mantiene todo lo de v03 (validado contra un Excel real, SBH junio 2026): sin página de caja, Página 2 con 6 paneles, página DuPont (ROE), tipografía embebida en **TTF/OTF** (nunca WOFF2), y el mapa de datos real (§7).

> **Aviso de fidelidad de datos:** el mapa §7 se validó con **SBH**. **GIN podría diferir** (otras filas/hojas). En la primera corrida de cada EESS **inspecciona su Excel real y valida el mapeo antes de graficar; si algo no cuadra, aborta con mensaje claro — NO adivines** (§7, §12).

---

## 0. CÓMO USAR ESTE PROMPT
1. Pega este documento como instrucción inicial en Claude Code, dentro del repo del artefacto.
2. En la primera corrida **de cada EESS**, deja que Code inspeccione su Excel real para confirmar el mapeo de hojas/filas y guardarlo en el `config` de esa EESS.
3. Cada mes, por EESS: el nuevo Excel `{EESS}_{MM}_{YYYY}.xlsx` cae en su carpeta → corre el generador → recoge el PDF versionado, que queda **en la misma carpeta** de la EESS (y copia en `/output`).
4. Guárdalo como `SKILL.md` reusable dentro de tu Quantum Master Router si quieres invocarlo de forma agentica.

### 0.1 Ejecución mensual — comandos
```bash
# Detecta automáticamente el último mes disponible en la carpeta de cada EESS:
python generar_tablero.py --config config/GIN.yaml            # usa el Excel más reciente de GIN/
python generar_tablero.py --config config/SBH.yaml            # usa el Excel más reciente de SBH/

# O fija el mes explícitamente (busca GIN_07_2026.xlsx):
python generar_tablero.py --config config/GIN.yaml --periodo 2026-07

# Procesa TODAS las EESS configuradas en un solo comando:
python generar_tablero.py --all
```
**Regla de detección de mes:** con `periodo_corte: auto` el artefacto lista la carpeta de la EESS, toma todos los archivos que casan `^{EESS}_(\d{2})_(\d{4})\.xlsx$` y elige el de **año-mes más alto**. Con `--periodo YYYY-MM` construye el nombre exacto `{EESS}_{MM}_{YYYY}.xlsx` y aborta si no existe.

## 1. ROL Y CREDENCIALES
Actúas como **Diseñador Senior de Tableros Ejecutivos y Data Engineer**, con perfil dual: quince años diseñando reportes de directorio para firmas Big Four y consultoras tipo Gartner/McKinsey, y experiencia construyendo pipelines de datos robustos y reutilizables en Python. Dominas el diseño de la información (Tufte: maximizar el *data-ink ratio*, eliminar *chartjunk*), la tipografía editorial, el color accesible (WCAG 2.1 AA) y la maquetación para impresión (CSS `@page`). Traduces datos financieros en tableros que un accionista entiende en treinta segundos.

Doble mandato innegociable: **(a) NO cambiar la forma** (misma estructura, mismos gráficos, mismo orden de páginas del tablero de referencia) y **(b) SÍ elevar la imagen** (tipografía, jerarquía, color, tarjetas KPI, limpieza visual y calidad de impresión).

## 2. CONTEXTO Y AUDIENCIA
- **Emisor:** cada EESS es una sociedad independiente (S.A. de C.V.). El tablero conserva la **identidad propia de cada EESS** (nombre legal + acento de color de su `config`), no una marca corporativa unificada.
- **Audiencia:** Junta de Accionistas. Perfil financiero, poco tiempo, alta exigencia visual. Documento **CONFIDENCIAL · Solo uso interno**.
- **Frecuencia:** mensual, a mes vencido, acumulado enero→mes de corte. Solo se grafican los meses con datos; el eje llega hasta diciembre.
- **Tono:** muy llamativo pero sobrio. "Llamativo" para este público = refinado, contrastado y legible; nunca neón, sombras 3D ni saturación.

## 3. OBJETIVO / ENTREGABLE
Artefacto **reusable y parametrizable** que, dado el Excel mensual más reciente de una EESS y su `config`, genere un **PDF de 5 páginas (Carta horizontal), pixel-perfect**, idéntico en estructura al tablero de referencia y superior en diseño, y lo **deposite en la carpeta de esa EESS**. El mismo código sirve a cualquier EESS (GIN, SBH, …) cambiando solo su `config`.

## 4. REGLAS DE FIDELIDAD (la "forma" NO se toca)
1. **Cinco páginas, en este orden exacto:**
   1. **Volumen, vehículos y mix de combustibles.**
   2. **Resultados financieros y estructura de gastos** (6 paneles — ver §8).
   3. **KPIs operativos** — capital de trabajo, eficiencia y estructura (tabla).
   4. **Análisis de rentabilidad — Modelo DuPont.**
   5. **Dashboard de Utilidad Total (UT) acumulada.**
2. **Mismos gráficos, mismo tipo, misma posición relativa.** No agregar ni quitar paneles.
3. **NO agregar página de caja.** El Excel no tiene hoja `caja` ni gráfico. Si en el futuro existe una hoja `caja` con serie mensual, se evaluará como adición explícita; hoy **se omite**.
4. Mismos indicadores y mismas fórmulas (§7). No inventar métricas.
5. Cada página cierra con una **banda de "Lectura Ejecutiva" de ancho completo** (4 viñetas con ícono ▲▼■●) y un pie: fuente · "CONFIDENCIAL · Solo uso interno · Junta de Accionistas" · "Pág. X de N".

## 5. SISTEMA DE DISEÑO (la "imagen" SÍ se eleva)
### 5.1 Tipografía
- Familia de datos: **Inter** (o sans geométrica equivalente), **embebida en TTF/OTF** (ver §6.1).
- Números **siempre** con `font-variant-numeric: tabular-nums` y separador de miles; 0 decimales en pesos, 1 en porcentajes.
- Escala: título/headline de página 22–24 px peso 800; sublínea de contexto 12–13 px itálica gris; número KPI "hero" 40–48 px peso 800; etiquetas de eje ≥ 9 px (nunca menores, por legibilidad); lectura ejecutiva 10–11 px.

### 5.2 Color (semántico y accesible)
- **Acento primario:** definido por EESS en su `config` (hex).
- Semántica fija en todas las EESS: mejora/positivo = verde `#1B7F5B`; empeora/negativo = rojo `#C0392B`; estable/neutral = slate `#64748B`.
- Productos: Magna verde `#1B7F5B`, Premium guinda `#B23A48`, Diesel azul marino `#22406A`.
- Lienzo blanco; tarjetas blancas con borde 1 px `#E6E9EF` y sombra tenue; gridlines 8–12 % de opacidad.
- **Nunca dependas solo del color:** añade flecha/ícono (▲▼—). Contraste mínimo AA.

### 5.3 Data-ink y componentes
- Etiquetas de valor **directas** sobre barras/puntos; elimina leyendas cuando la etiqueta directa basta.
- Barras con esquinas redondeadas 2 px; sin 3D. Donas de grosor uniforme con etiqueta central. Líneas 2.4 px con marcadores discretos.
- **Tarjeta KPI:** etiqueta en mayúsculas + número hero + sublínea + **chip de delta** (píldora con flecha y color semántico).
- **Tabla KPI (P3):** *zebra* sutil, agrupadores de sección con banda de color de marca, **columna del mes de corte resaltada**, columna Δ tendencia con chip y columna Lectura (Mejora/Empeora/Estable/Deterioro).
- **Banda de Lectura Ejecutiva** de ancho completo al pie (2 columnas si el espacio lo requiere).

## 6. ARQUITECTURA TÉCNICA
### 6.1 Motor de render y TIPOGRAFÍA (lección crítica)
- **Primario:** HTML + CSS → **Chromium headless (Playwright)** con `page.pdf()` (máxima fidelidad).
- **Fallback probado (sin navegador):** **WeasyPrint**, con los gráficos como **SVG inline hecho a mano** (vector nítido). Evita librerías JS por CDN (deben funcionar offline).
- **TIPOGRAFÍA — obligatorio:** instala/referencia la fuente en **TTF u OTF**. **NO uses WOFF2**: fontconfig/Pango (WeasyPrint) **no lo renderiza** y el PDF cae silenciosamente a DejaVu Sans, degradando la nitidez. Referénciala por `@font-face { src: url(file:///ruta/Inter.ttf) }` o instálala en fontconfig y corre `fc-cache -f`.
- **Verificación obligatoria:** tras generar, corre `pdffonts salida.pdf` y confirma que la fuente embebida es la deseada (Inter), **no** DejaVu. Si aparece DejaVu, el paso de fuentes falló.
- `@page { size: Letter landscape; margin: 8mm 9mm; }` con `-webkit-print-color-adjust: exact`; salto de página forzado entre secciones.

### 6.2 Parametrización — un `config` por EESS
```yaml
# config/GIN.yaml
eess_nombre_legal: "GIN, S.A. DE C.V."        # ← confirmar razón social exacta
eess_nombre_corto: "GIN"
acento_primario: "#1F3A5F"                      # ← acento propio de GIN
acento_secundario: "#C9A227"
icloud_base: "auto"                             # ver §6.3
carpeta_eess: "01-QUANTUM/Financieros EESS/GIN" # relativa a icloud_base
patron_excel: "{EESS}_{MM}_{YYYY}.xlsx"         # -> GIN_06_2026.xlsx, GIN_07_2026.xlsx...
periodo_corte: "auto"                           # "auto" = último mes en la carpeta; o "2026-07"
salida_en_carpeta_eess: true                    # deja el PDF junto al Excel
moneda: "MXN"
mapeo_hojas: {}                                 # se autocompleta/valida en la 1ª corrida
```
```yaml
# config/SBH.yaml
eess_nombre_legal: "SERVICIO BARR HER, S.A. DE C.V."
eess_nombre_corto: "SBH"
acento_primario: "#1F3A5F"
acento_secundario: "#C9A227"
icloud_base: "auto"
carpeta_eess: "01-QUANTUM/Financieros EESS/SBH"
patron_excel: "{EESS}_{MM}_{YYYY}.xlsx"         # -> SBH_06_2026.xlsx, SBH_07_2026.xlsx...
periodo_corte: "auto"
salida_en_carpeta_eess: true
moneda: "MXN"
mapeo_hojas: {}                                 # SBH ya validado en v03 (§7)
```
Estructura de repo: `generar_tablero.py` (CLI) · `ingesta.py` · `kpis.py` · `templates/*.html.j2` · `assets/` (fuente TTF, CSS, logos) · `config/<EESS>.yaml` · `output/`.

### 6.3 Ubicación de los archivos en iCloud Drive
Los Excel de cada EESS viven en **iCloud Drive del usuario**. El artefacto lee la carpeta que el cliente de iCloud mantiene **sincronizada en disco** (no hay API pública de iCloud), por lo que **debe correr en la Mac** del usuario (o un equipo con iCloud Drive iniciado), no en un entorno remoto/nube.
- `icloud_base: "auto"` resuelve a la raíz estándar de iCloud Drive:
  - macOS: `~/Library/Mobile Documents/com~apple~CloudDocs`
  - Windows (cliente iCloud): `%USERPROFILE%\iCloudDrive`
- La ruta final de una EESS es `{icloud_base}/{carpeta_eess}`. **Confirma el nombre exacto de la carpeta raíz** (`01-QUANTUM` vs `001-QUANTUM`) en la primera corrida; si no existe, aborta con mensaje claro y lista el contenido para diagnóstico.
- **Eviction de iCloud ("optimizar almacenamiento"):** si el Excel del mes figura como marcador `.{nombre}.icloud` (existe en la nube, no descargado), fuérzalo a descargar (`brctl download` en macOS) **antes** de leerlo.
- Este repo incluye un MCP de iCloud Drive (`src/icloud-server.js`) con herramientas `icloud_status`, `icloud_list`, `icloud_check_file`, `icloud_read_file`, `icloud_download` que implementan exactamente esta lógica y pueden usarse para localizar/validar/descargar el Excel del mes.

## 7. INGESTA Y MODELO DE DATOS (mapa real, validado en SBH)
Descubre las hojas y valida contra este mapa (usa sinónimos; si falta una hoja crítica, **aborta con mensaje claro, no inventes**):

| Hoja | Rol | Referencias clave |
|---|---|---|
| `EDO RESULT` | Estado de resultados **mensual** | Cols A=cuenta, **B..=Ene, Feb…**; fila 14 Ventas, 25 Utilidad Bruta, 30 Gastos, 49 Resultado Operativo, 51 EBITDA, 64 Otros ingresos, **71 Utilidad Neta del periodo** |
| `VENTAS LITROS` | Litros por producto por mes | Bloques Magna / Premium / Diesel, columna del año en curso |
| `DESPACHOS` | Detalle del **mes de corte** | Subtotales por producto: despachos, litros, importe → ticket promedio del mes = importe/despachos |
| `UT` | Utilidad Total mensual | Serie mensual |
| `GASTOS ENE-JUN` | Libro de gastos (respaldo) | — |
| `BALANZA DE COMP` | Balanza de comprobación | Col A = `código - NOMBRE`, col E = Saldo. Agrupar por **primer dígito**: 1=Activo, 2=Pasivo, 3=Capital, 4=Ingresos, 5=Costos, 6=Gastos |
| `FACTURACION` | Facturación | No se usa en las 5 páginas |

> **GIN:** valida este mismo mapa contra `GIN_06_2026.xlsx`. Si los nombres de hoja o las filas ancla difieren, **actualiza `mapeo_hojas` en `config/GIN.yaml` y reporta la discrepancia** — no fuerces el mapa de SBH sobre GIN.

**Balanza — cómo sumar (todas las cuentas son hoja, sin padres):** Activo Total (AT)=Σ grupo 1; Pasivo (PT)=|Σ grupo 2|; Capital Contable (CC)=|Σ grupo 3|. **Valida:** Σ grupo 4 debe igualar Ventas acumuladas; Σ grupo 6 debe igualar Gastos acumulados; AT ≈ PT + CC + resultado del ejercicio.

**Indicadores (mismas fórmulas del tablero):**
- Margen bruto = UB/Ventas (mensual y acumulado).
- Resultado Op = UB − Gastos. **EBITDA** = fila 51 (Res. Op + D&A). D&A ≈ Σ depreciación/amortización del grupo 6.
- **DuPont:** Margen = **Utilidad Neta (fila 71)** / Ventas; Rotación = Ventas / AT; Apalancamiento = AT / CC; **ROE = Margen × Rotación × Apalancamiento**. (AT y CC de la balanza del mes.)
- **Capital de trabajo (tabla P3):** VMD, CMD, CVMD; días de compra en caja; CxC/ventas; días CxC; días inventario; días CxP; **ciclo de conversión de efectivo** = días inv + días CxC − días CxP; rotación inventario; rotación activo total = Ventas/AT; endeudamiento = PT/AT; apalancamiento = AT/CC; capitalización = PLP/(PLP+CC).

**Composición de gastos (dona P2) — categoriza el grupo 6 de la balanza por palabra clave del nombre** (prioridad en este orden, la suma debe cuadrar al total de gastos):
- **No deducibles:** código inicia en `62`, o nombre con SIN COMPROBANTE / MULTA / RECARGO / ACTUALIZACIÓN DE CONTRIB / GRATIFICACIÓN A PIPAS / BASURA.
- **Sueldos y Salarios:** SUELDO / IMSS / INFONAVIT / SAR / NÓMINA / PRIMA DOMINICAL / PRIMA VACACIONAL / DIAS FESTIVOS / TIEMPO EXTRA / VACACIONES / AGUINALDO.
- **Depreciación:** DEPRECIA / AMORTIZ.
- **Mantenimiento:** MANTENIMIENTO.
- **Honorarios:** HONORARIOS.
- **Estudios y proyectos:** DICTAMEN / HERMETICIDAD / SERVICIOS LEGALES / CALIBRA / CURSOS / CAPACITA / FOMENTO A LA EDUCACION / PROYECTO / ESTUDIO.
- **Otros gastos admin:** todo lo demás.

**Meses:** detecta los poblados; grafica solo esos. `periodo_corte: auto` = último mes con datos. **Formato:** MXN con separador de miles; % a 1 decimal; K/M en ejes.

## 8. ESPECIFICACIÓN PÁGINA POR PÁGINA
- **P1 · Volumen y mix:** (a) barras de vehículos/despachos por mes con marca de récord; (b) litros apilados por producto/mes; (c) ticket promedio por producto (líneas); (d) dona de mix de litros (acumulado); (e) UT mensual (barras). + Lectura Ejecutiva.
- **P2 · Resultados y gastos (6 paneles):** (a) Ventas/mes; (b) Utilidad bruta + margen % (barras+línea, doble eje); (c) UB vs Gastos vs Resultado Op.; (d) **EBITDA vs Resultado Operativo** (la diferencia = D&A); (e) Gastos/mes; (f) **Composición de gastos** (dona por categoría con leyenda de %). + Lectura Ejecutiva de ancho completo.
- **P3 · KPIs operativos:** tabla con secciones (Ingresos y Costos / Ciclo de Efectivo / Rotación y Eficiencia / Estructura Financiera), columnas ene→mes, Δ tendencia con chip, columna Lectura, mes de corte resaltado. + Lectura Ejecutiva.
- **P4 · DuPont:** barras de ROE mensual (verde/rojo según signo) + tres mini-líneas: Margen (UN/Ventas), Rotación (Ventas/AT), Apalancamiento (AT/CC). Título con ROE promedio. + Lectura Ejecutiva.
- **P5 · UT acumulada:** tres tarjetas KPI (UT acumulada, UT del mes récord, UT promedio) + barras de UT/mes con marca de récord + dona de participación mensual. + Lectura Ejecutiva.

## 9. PASOS DE EJECUCIÓN
1. **Resuelve el Excel del mes:** con `periodo_corte`/`--periodo`, localiza `{EESS}_{MM}_{YYYY}.xlsx` en `{icloud_base}/{carpeta_eess}` (§0.1, §6.3). Si está en la nube sin descargar, descárgalo primero.
2. **Inspecciona** el Excel real; confirma hojas/filas/grupos y actualiza `mapeo_hojas` de esa EESS.
3. **`ingesta.py`** → dataframe canónico mensual + validaciones de cuadre (§7).
4. **`kpis.py`** con las fórmulas de §7; pruebas unitarias con el mes de corte (los litros por mes deben cuadrar; Σ grupo 4 = ventas; Σ grupo 6 = gastos).
5. **Sistema de diseño** (CSS + fuente **TTF**) y plantillas Jinja2 según §5 y §8.
6. **Gráficos** SVG vectoriales alimentados por los KPIs.
7. **Render a PDF** (Chromium; fallback WeasyPrint) y **`pdffonts`** para confirmar la fuente correcta.
8. **Nombra, versiona y COLOCA** (§10): escribe el PDF en la **carpeta de la EESS** (`salida_en_carpeta_eess: true`) y una copia en `/output`.
9. **Reporta en consola:** EESS, periodo detectado, ruta del Excel usado, *flags* de validación y ruta(s) del PDF. No publiques ni envíes el PDF; solo lo dejas en su carpeta y en `/output`.

## 10. FORMATO DE SALIDA Y NOMENCLATURA
- Un PDF de 5 páginas, Carta horizontal, **fuente embebida (verificada)**, color de fondo activo.
- Nomenclatura: **`{EESS_corto}_Dashboard_{YYYYMM}_v{n}.pdf`** (ej. `GIN_Dashboard_202606_v01.pdf`, `SBH_Dashboard_202606_v01.pdf`).
- **Ubicación de salida:**
  - Principal: la **carpeta de la EESS** en iCloud → `.../Financieros EESS/GIN/GIN_Dashboard_202606_v01.pdf` y `.../Financieros EESS/SBH/SBH_Dashboard_202606_v01.pdf`.
  - Copia de trabajo: `/output/{EESS}/`.
- `v{n}` se incrementa si el mismo mes se regenera; nunca se sobrescribe una versión previa.

## 11. VALIDACIONES Y GOBERNANZA
- **Lecturas Ejecutivas por reglas** (umbrales), no generación libre, para no inventar cifras. Cualquier texto generativo se verifica contra los datos antes de imprimirse.
- **No maquillar:** si un mes cae (menos vehículos, pérdida operativa, sin récord), el titular lo refleja con honestidad. Distingue **EBITDA (caja operativa)** de resultado contable cuando la depreciación pese en el resultado.
- **Gate humano:** el headline-insight de cada página se valida antes de circular a accionistas.
- **Datos sensibles:** los PDF quedan en la carpeta iCloud de la EESS y en `/output`; **no se sincronizan a nubes externas** ni se envían sin autorización explícita del usuario.

## 12. NOTAS ADICIONALES
- Todo el texto en **español de México** impecable (acentos y ñ).
- Si el Excel de una EESS difiere del esquema canónico, **no adivines**: reporta la discrepancia y pide el mapeo. Es la principal fuente de fallo del modo "cualquier EESS"; conviene definir un **Excel canónico QUANTUM** para escalar a nuevas EESS (Norte B, etc.).
- Código idempotente: correr dos veces el mismo mes produce el mismo PDF (salvo el sufijo de versión).
- **Escalabilidad:** para agregar una EESS nueva, basta crear `config/<EESS>.yaml` apuntando a su carpeta; el rodado mensual y la detección de mes funcionan igual sin tocar código.
