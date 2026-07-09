# Generador de Tableros EESS

Convierte el Excel financiero mensual de una Estación de Servicio (EESS) en un
**PDF de 5 páginas** (Carta horizontal) para la Junta de Accionistas, según el
prompt maestro [`prompts/PROMPT_Generador_Tableros_EESS_v04.md`](../prompts/PROMPT_Generador_Tableros_EESS_v04.md).

Páginas: **1** Volumen y mix · **2** Resultados y estructura de gastos (6 paneles) ·
**3** KPIs operativos (tabla) · **4** Rentabilidad DuPont · **5** Utilidad Total (UT).

## Cómo funciona

- **Ingesta robusta** (`ingesta.py`): localiza hojas por sinónimos y filas por
  etiqueta (no por número fijo), porque las EESS difieren — p. ej. la Utilidad
  Neta cae en la fila 71 en SBH y en la 70 en GIN. Valida cuadres: Σ grupo 4 de
  la balanza = ventas, Σ grupo 6 = gastos.
- **KPIs** (`kpis.py`): márgenes, EBITDA, capital de trabajo, DuPont (ROE).
- **Gráficos** (`charts.py`): SVG vectorial hecho a mano (nítido en PDF, sin JS/CDN).
- **Render** (`render_pdf.mjs`): Chromium headless (Playwright) → `page.pdf()`.
  Fuente **Inter embebida en TTF** (`assets/fonts/Inter.ttf`), nunca WOFF2.

## Uso

```bash
pip install -r requirements.txt
npm install                     # en la raíz del repo (trae playwright)

# Un mes concreto (busca SBH_06_2026.xlsx en la carpeta iCloud de la config):
python generar_tablero.py --config config/SBH.yaml --periodo 2026-06

# Detección automática del último mes disponible en la carpeta:
python generar_tablero.py --config config/GIN.yaml

# Ambas EESS de un jalón:
python generar_tablero.py --all

# Con un Excel explícito (útil para probar fuera de iCloud):
python generar_tablero.py --config config/SBH.yaml --excel /ruta/SBH_06_2026.xlsx
```

El PDF se nombra `{EESS}_Dashboard_{YYYYMM}_v01.pdf` y se deja en la carpeta de
la EESS en iCloud (si `salida_en_carpeta_eess: true` y la carpeta existe) y en
`output/{EESS}/`.

## Requisitos e importante

- **Corre en una máquina con iCloud Drive sincronizado** (Mac): lee la carpeta
  local `~/Library/Mobile Documents/com~apple~CloudDocs/...`. No funciona en un
  entorno de nube que no ve tu iCloud.
- Node ≥ 20 (para Playwright) y Python ≥ 3.11.
- `pip install pymupdf` opcional, solo para previsualizar el PDF como imagen.

## Automatización (opción B — al soltar el archivo, en tu Mac)

Un watcher `launchd` genera el PDF **en cuanto sueltas** `GIN_07_2026.xlsx` o
`SBH_07_2026.xlsx` (o el mes que sea) en la carpeta de la EESS.

```bash
bash tablero/watch/instalar_mac.sh      # instala dependencias + servicio launchd
```

Qué hace:
- Vigila las carpetas de EESS que resuelven las `config/*.yaml` (vía `WatchPaths`).
- Al cambiar el contenido, corre `watch/procesar_nuevos.py`, que toma el Excel
  del **último mes**, y genera el PDF **solo si es más nuevo** que el existente
  (idempotente, no entra en bucle al escribir el PDF).
- Si el Excel llegó como marcador `.icloud` (en la nube, sin descargar), lo baja
  con `brctl download` y espera a que se materialice.
- Arranca al iniciar sesión y se reactiva solo. Registro en `watch/watcher.log`.

```bash
bash tablero/watch/desinstalar_mac.sh   # quitar el servicio
```

> Debe correr en la Mac donde está iCloud sincronizado. Añadir una EESS nueva:
> crea su `config/<EESS>.yaml` y vuelve a correr el instalador para que vigile
> también esa carpeta.

## Añadir una EESS nueva

Crea `config/<EESS>.yaml` apuntando a su carpeta y acento de color. El rodado
mensual y la detección del mes funcionan sin tocar código. Si su Excel difiere
del esquema canónico, la ingesta lo reporta en vez de adivinar (§7/§12 del prompt).
