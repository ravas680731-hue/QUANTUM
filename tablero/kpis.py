"""Cálculo de KPIs a partir del modelo canónico (§7 del prompt)."""
from __future__ import annotations
import calendar


def _acc(series, n):
    return sum(series[:n])


def compute(model: dict, anio: int = 2026) -> dict:
    n = model["n_meses"] or 6
    b = model["balanza"]
    AT, PT, CC = b["AT"], b["PT"], b["CC"]
    ventas = model["ventas"]; costo = model["costo"]; gastos = model["gastos"]
    ub = model["utilidad_bruta"]; resop = model["resultado_op"]
    ebitda = model["ebitda"]; un = model["utilidad_neta"]; ut = model["ut"]

    ventas_acum = _acc(ventas, n); costo_acum = _acc(costo, n)
    ub_acum = _acc(ub, n); gastos_acum = _acc(gastos, n); un_acum = _acc(un, n)

    dias = sum(calendar.monthrange(anio, m)[1] for m in range(1, n + 1))

    margen_mes = [ (ub[i]/ventas[i] if ventas[i] else 0.0) for i in range(12) ]
    margen_acum = ub_acum/ventas_acum if ventas_acum else 0.0

    VMD = ventas_acum/dias if dias else 0.0
    CMD = costo_acum/dias if dias else 0.0

    rot_activo = ventas_acum/AT if AT else 0.0
    endeudamiento = PT/AT if AT else 0.0
    apalancamiento = AT/CC if CC else 0.0
    capitalizacion = b["PLP"]/(b["PLP"]+CC) if (b["PLP"]+CC) else 0.0

    dias_cxc = b["CxC"]/VMD if VMD else 0.0
    dias_inv = b["inventario"]/CMD if CMD else 0.0
    dias_cxp = min(b["CxP"], PT)/CMD if CMD else 0.0
    ciclo = dias_inv + dias_cxc - dias_cxp
    rot_inv = costo_acum/b["inventario"] if b["inventario"] else 0.0

    # DuPont
    dp_margen = un_acum/ventas_acum if ventas_acum else 0.0
    dp_rot = ventas_acum/AT if AT else 0.0
    dp_apal = AT/CC if CC else 0.0
    roe_acum = dp_margen*dp_rot*dp_apal
    roe_mes = [ (un[i]/CC if CC else 0.0) for i in range(12) ]        # UN_m/CC
    margen_un_mes = [ (un[i]/ventas[i] if ventas[i] else 0.0) for i in range(12) ]
    rot_mes = [ (ventas[i]/AT if AT else 0.0) for i in range(12) ]

    litros = model["litros"]
    litros_tot_mes = [ litros["Magna"][i]+litros["Premium"][i]+litros["Diesel"][i] for i in range(12) ]
    mix = { p: _acc(litros[p], n) for p in litros }

    ut_acum = _acc(ut, n)
    ut_mes_validos = [ut[i] for i in range(n)]
    ut_record_i = max(range(n), key=lambda i: ut[i]) if n else 0
    ut_prom = ut_acum/n if n else 0.0

    return dict(
        n=n, dias=dias,
        ventas_acum=ventas_acum, costo_acum=costo_acum, ub_acum=ub_acum,
        gastos_acum=gastos_acum, un_acum=un_acum,
        margen_mes=margen_mes, margen_acum=margen_acum,
        VMD=VMD, CMD=CMD,
        rot_activo=rot_activo, endeudamiento=endeudamiento,
        apalancamiento=apalancamiento, capitalizacion=capitalizacion,
        dias_cxc=dias_cxc, dias_inv=dias_inv, dias_cxp=dias_cxp,
        ciclo=ciclo, rot_inv=rot_inv,
        dp_margen=dp_margen, dp_rot=dp_rot, dp_apal=dp_apal,
        roe_acum=roe_acum, roe_mes=roe_mes,
        margen_un_mes=margen_un_mes, rot_mes=rot_mes,
        litros_tot_mes=litros_tot_mes, mix=mix,
        ut_acum=ut_acum, ut_record_i=ut_record_i, ut_prom=ut_prom,
        resultado_op_acum=_acc(resop, n), ebitda_acum=_acc(ebitda, n),
    )
