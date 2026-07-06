# Seguridad — NotebookLM MCP (uso interno)

Resumen claro de qué hace y qué NO hace este servidor con tus datos. Pensado
para uso interno de tu equipo.

## Qué datos se guardan y dónde

| Dato | Dónde se guarda | ¿Se sube a algún sitio? |
|------|-----------------|--------------------------|
| Tu sesión de Google (cookies) | **Solo en tu equipo**, en `~/.notebooklm-mcp/profile` | **No.** Nunca. Está en `.gitignore` |
| Usuario / contraseña de Google | **En ningún lado** — tú inicias sesión directamente en la ventana de Google | **No** los ve ni los guarda este software |
| Contenido de tus notebooks | No se almacena; solo se lee para responder tu pregunta en el momento | **No** |

## A dónde se conecta

- **Único destino de red:** `notebooklm.google.com` (el sitio oficial de Google).
- **No** hay conexiones ocultas, ni envío de datos a terceros, ni telemetría.
- Puedes verificarlo: no hay llamadas de red en el código fuente salvo la
  navegación del navegador a NotebookLM (revisa `src/`).

## Por qué se ejecuta en tu equipo (y no en una nube compartida)

Este servidor usa **tu propia sesión de Google**. La recomendación de seguridad
es ejecutarlo en **tu computador** (o en un equipo interno de confianza), no en
una nube compartida, para que tus cookies de Google no queden en un entorno
compartido. Así el acceso a tu cuenta nunca sale de tu control.

## Cadena de suministro (dependencias)

- Solo 2 dependencias directas, ambas oficiales: **Playwright** (Microsoft) y
  el **SDK de MCP** (Anthropic).
- `npm audit`: **0 vulnerabilidades**. Todas las dependencias provienen del
  registro oficial de npm con verificación de integridad (hash).

## Cómo revocar el acceso en cualquier momento

1. **Borrar la sesión local:** elimina la carpeta `~/.notebooklm-mcp/` — con eso
   el servidor deja de tener acceso y habría que iniciar sesión de nuevo.
2. **Revocar desde Google:** entra a
   [myaccount.google.com/security](https://myaccount.google.com/security) →
   "Tus conexiones a apps y dispositivos" y cierra la sesión del navegador
   automatizado.
3. **Quitar de Claude:** `claude mcp remove notebooklm` (o desaprobar el
   servidor en la configuración de MCP de Cowork).

## Buenas prácticas para tu equipo

- Usa una cuenta de Google dedicada al equipo si vas a compartir el uso.
- Mantén la carpeta del perfil (`~/.notebooklm-mcp/`) con permisos solo para tu
  usuario del sistema.
- No copies esa carpeta a otros equipos ni la subas a ningún repositorio.
