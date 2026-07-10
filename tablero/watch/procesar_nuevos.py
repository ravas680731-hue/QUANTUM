#!/usr/bin/env python3
"""
Procesa los Excel nuevos de cada EESS y genera su PDF (opción B: watcher).

Lo dispara launchd (WatchPaths) cada vez que cambia el contenido de una carpeta
de EESS. Recorre todas las config/*.yaml, resuelve el Excel más reciente
({EESS}_MM_YYYY.xlsx), y regenera el tablero SOLO si el Excel es más nuevo que
el PDF ya existente (idempotente: no entra en bucle al escribir el PDF).

Maneja la "optimización de almacenamiento" de iCloud: si el Excel llegó como
marcador `.NOMBRE.xlsx.icloud` (en la nube, sin descargar), lo baja con
`brctl download` y espera a que se materialice antes de leerlo.

Registra todo en watch/watcher.log.
"""
from __future__ import annotations
import os, sys, re, glob, time, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)               # .../tablero
sys.path.insert(0, ROOT)
import yaml                                 # noqa: E402
import generar_tablero as G                 # noqa: E402

LOG = os.path.join(HERE, "watcher.log")


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def materializar_icloud(folder, eess):
    """Si el Excel del último mes está como placeholder .icloud, descárgalo."""
    for f in glob.glob(os.path.join(folder, f".{eess}_*.xlsx.icloud")):
        real = os.path.join(folder, os.path.basename(f)[1:-len(".icloud")])
        log(f"iCloud: descargando {os.path.basename(real)} (estaba en la nube)…")
        subprocess.run(["brctl", "download", real], capture_output=True)
        for _ in range(60):
            if os.path.isfile(real):
                log(f"iCloud: {os.path.basename(real)} ya está local.")
                break
            time.sleep(1)


def excel_mas_reciente(cfg):
    folder = os.path.join(G.icloud_base(cfg), cfg["carpeta_eess"])
    eess = cfg["eess_nombre_corto"]
    if not os.path.isdir(folder):
        return None, None
    materializar_icloud(folder, eess)
    pat = re.compile(rf"^{re.escape(eess)}_(\d{{2}})_(\d{{4}})\.xlsx$", re.I)
    best = None
    for f in glob.glob(os.path.join(folder, "*.xlsx")):
        m = pat.match(os.path.basename(f))
        if m:
            key = (int(m.group(2)), int(m.group(1)))
            if best is None or key > best[0]:
                best = (key, f)
    if not best:
        return None, None
    (anio, mes), path = best
    return path, (anio, mes)


def pdf_actualizado(cfg, anio, mes, xls):
    """True si el tablero Y el anexo ya existen y son más nuevos que el Excel."""
    corto = cfg["eess_nombre_corto"]
    folder = os.path.join(G.icloud_base(cfg), cfg["carpeta_eess"])
    xls_mt = os.path.getmtime(xls)
    for name in (f"{corto}_Dashboard_{anio}{mes:02d}_v01.pdf",
                 f"{corto}_Anexo_Gastos_{anio}{mes:02d}_v01.pdf"):
        p = os.path.join(folder, name)
        if not (os.path.isfile(p) and os.path.getmtime(p) >= xls_mt):
            return False
    return True


def main():
    configs = sorted(glob.glob(os.path.join(ROOT, "config", "*.yaml")))
    hubo_trabajo = False
    for cfg_path in configs:
        try:
            cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
            xls, per = excel_mas_reciente(cfg)
            if not xls:
                continue
            anio, mes = per
            if pdf_actualizado(cfg, anio, mes, xls):
                continue
            log(f"[{cfg['eess_nombre_corto']}] nuevo/actualizado {os.path.basename(xls)} → generando…")
            out = G.run_one(cfg_path, periodo=f"{anio}-{mes:02d}")
            log(f"[{cfg['eess_nombre_corto']}] PDF listo: {out}")
            hubo_trabajo = True
        except SystemExit as e:
            log(f"[{os.path.basename(cfg_path)}] aviso: {e}")
        except Exception as e:
            log(f"[{os.path.basename(cfg_path)}] ERROR: {e!r}")
    if not hubo_trabajo:
        # Con sondeo cada 5 min no persistimos esto para no llenar el log;
        # solo a consola (útil al correrlo a mano).
        print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  sin cambios (todos los PDF al día).")


if __name__ == "__main__":
    main()
