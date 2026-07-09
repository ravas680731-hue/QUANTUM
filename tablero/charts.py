"""Gráficos SVG vectoriales, hechos a mano (nítidos en PDF, sin JS/CDN)."""
from __future__ import annotations
import html

POS = "#1B7F5B"; NEG = "#C0392B"; NEU = "#64748B"
INK = "#0F172A"; MUTE = "#64748B"; GRID = "rgba(15,23,42,0.08)"
PROD = {"Magna": "#1B7F5B", "Premium": "#B23A48", "Diesel": "#22406A"}


def money_c(v, sign=True):
    a = abs(v); s = "-" if v < 0 else ""
    p = "$" if sign else ""
    if a >= 1e6: return f"{s}{p}{a/1e6:.1f}M"
    if a >= 1e3: return f"{s}{p}{a/1e3:.0f}K"
    return f"{s}{p}{a:.0f}"


def num_c(v):
    a = abs(v); s = "-" if v < 0 else ""
    if a >= 1e6: return f"{s}{a/1e6:.1f}M"
    if a >= 1e3: return f"{s}{a/1e3:.0f}K"
    return f"{s}{a:.0f}"


def pct(v, d=1): return f"{v*100:.{d}f}%"


def _t(x, y, s, size=10, col=MUTE, anchor="middle", weight=400, style=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{col}" '
            f'text-anchor="{anchor}" font-weight="{weight}" {style}>{html.escape(str(s))}</text>')


def _frame(w, h):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
            f'preserveAspectRatio="xMidYMid meet" '
            f'style="position:absolute;inset:0;width:100%;height:100%" '
            f'font-family="Inter, sans-serif">')


def _flabel(v, fmt):
    if fmt == "money": return money_c(v)
    if fmt == "pct": return pct(v)
    if fmt == "mult": return f"{v:.2f}×"
    return num_c(v)


def bars(values, labels, accent="#1F3A5F", fmt="money", record=False,
         w=440, h=330, semantic=False):
    """Barras verticales con línea base en cero (soporta negativos)."""
    L, R, T, B = 8, 8, 24, 28
    pw, ph = w - L - R, h - T - B
    vmax = max(values + [0.0]); vmin = min(values + [0.0])
    rng = (vmax - vmin) or 1.0
    y0 = T + (vmax - 0) / rng * ph
    n = len(values); gap = pw / n
    bw = min(gap * 0.6, 48)
    mlab_y = h - 8
    s = [_frame(w, h)]
    s.append(f'<line x1="{L}" y1="{y0:.1f}" x2="{w-R}" y2="{y0:.1f}" stroke="{GRID}" stroke-width="1"/>')
    imax = values.index(vmax) if record and vmax > 0 else -1
    for i, v in enumerate(values):
        cx = L + gap * (i + 0.5)
        y = T + (vmax - v) / rng * ph
        top = min(y, y0); bh = abs(y - y0)
        col = accent
        if semantic: col = POS if v >= 0 else NEG
        s.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bh,0.5):.1f}" '
                 f'rx="2" fill="{col}"/>')
        lbl = _flabel(v, fmt)
        if v >= 0:
            ly = max(top - 4, T - 2)
        else:
            ly = min(top + bh + 11, mlab_y - 11)
        s.append(_t(cx, ly, lbl, size=9.5, col=INK, weight=700))
        if i == imax:
            s.append(_t(cx, max(top - 13, T - 11), "▲ récord", size=8, col=accent, weight=700))
        s.append(_t(cx, mlab_y, labels[i], size=9.5, col=MUTE))
    s.append("</svg>")
    return "".join(s)


def bar_line(values, line_vals, labels, accent="#1F3A5F", w=440, h=330):
    """Barras (importe) + línea (porcentaje, eje derecho)."""
    L, R, T, B = 8, 8, 22, 22
    pw, ph = w - L - R, h - T - B
    vmax = max(values + [0.0]); vmin = min(values + [0.0]); rng = (vmax - vmin) or 1
    y0 = T + (vmax) / rng * ph
    n = len(values); gap = pw / n; bw = min(gap * 0.6, 44)
    lmax = max(line_vals) or 1; lmin = min(line_vals + [0])
    lrng = (lmax - lmin) or 1
    s = [_frame(w, h)]
    s.append(f'<line x1="{L}" y1="{y0:.1f}" x2="{w-R}" y2="{y0:.1f}" stroke="{GRID}"/>')
    pts = []
    for i, v in enumerate(values):
        cx = L + gap * (i + 0.5)
        y = T + (vmax - v) / rng * ph
        s.append(f'<rect x="{cx-bw/2:.1f}" y="{min(y,y0):.1f}" width="{bw:.1f}" height="{abs(y-y0):.1f}" rx="2" fill="{accent}" opacity="0.85"/>')
        s.append(_t(cx, min(y, y0) - 4, money_c(v), size=8.5, col=INK, weight=700))
        ly = T + (lmax - line_vals[i]) / lrng * ph * 0.8 + ph * 0.06
        pts.append((cx, ly))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.append(f'<path d="{d}" fill="none" stroke="{POS}" stroke-width="2.4"/>')
    for i, (x, y) in enumerate(pts):
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{POS}"/>')
        s.append(_t(x, y - 6, pct(line_vals[i]), size=8, col=POS, weight=700))
    for i in range(len(values)):
        s.append(_t(L + gap * (i + 0.5), h - 7, labels[i], size=9, col=MUTE))
    s.append("</svg>")
    return "".join(s)


def grouped(series: dict, labels, colors, w=440, h=330, money=True):
    L, R, T, B = 8, 8, 20, 30
    pw, ph = w - L - R, h - T - B
    allv = [v for s in series.values() for v in s] + [0.0]
    vmax = max(allv); vmin = min(allv); rng = (vmax - vmin) or 1
    y0 = T + vmax / rng * ph
    keys = list(series); m = len(keys); n = len(labels)
    gap = pw / n; bw = min((gap * 0.72) / m, 15)
    s = [_frame(w, h)]
    s.append(f'<line x1="{L}" y1="{y0:.1f}" x2="{w-R}" y2="{y0:.1f}" stroke="{GRID}"/>')
    for i in range(n):
        base = L + gap * i + (gap - bw * m) / 2
        for j, k in enumerate(keys):
            v = series[k][i]; x = base + j * bw
            y = T + (vmax - v) / rng * ph
            s.append(f'<rect x="{x:.1f}" y="{min(y,y0):.1f}" width="{bw*0.86:.1f}" height="{max(abs(y-y0),0.5):.1f}" rx="1.5" fill="{colors[j]}"/>')
        s.append(_t(L + gap * (i + 0.5), h - 16, labels[i], size=9, col=MUTE))
    lx = L
    for j, k in enumerate(keys):
        s.append(f'<rect x="{lx}" y="{h-9}" width="9" height="9" rx="2" fill="{colors[j]}"/>')
        s.append(_t(lx + 12, h - 1.5, k, size=8.5, col=MUTE, anchor="start"))
        lx += 14 + len(k) * 5.6
    s.append("</svg>")
    return "".join(s)


def stacked(series: dict, labels, w=440, h=330):
    L, R, T, B = 8, 8, 16, 30
    pw, ph = w - L - R, h - T - B
    totals = [sum(series[k][i] for k in series) for i in range(len(labels))]
    vmax = max(totals) or 1
    n = len(labels); gap = pw / n; bw = min(gap * 0.6, 44)
    s = [_frame(w, h)]
    for i in range(n):
        cx = L + gap * (i + 0.5); yb = T + ph
        for k in series:
            v = series[k][i]; hh = v / vmax * ph
            yb -= hh
            s.append(f'<rect x="{cx-bw/2:.1f}" y="{yb:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="{PROD[k]}"/>')
        s.append(_t(cx, T + ph + 13, labels[i], size=9, col=MUTE))
        s.append(_t(cx, T + ph - totals[i]/vmax*ph - 4, num_c(totals[i]), size=8.5, col=INK, weight=700))
    lx = L
    for k in series:
        s.append(f'<rect x="{lx}" y="{h-9}" width="9" height="9" rx="2" fill="{PROD[k]}"/>')
        s.append(_t(lx + 12, h - 1.5, k, size=8.5, col=MUTE, anchor="start"))
        lx += 16 + len(k) * 5.8
    s.append("</svg>")
    return "".join(s)


def donut(parts: dict, w=320, h=300, colors=None, center=None, csub=None):
    import math
    cx, cy, r, rin = w * 0.34, h * 0.5, min(w, h) * 0.34, min(w, h) * 0.2
    total = sum(parts.values()) or 1
    colors = colors or [PROD.get(k, ["#1F3A5F", "#1B7F5B", "#B23A48", "#22406A",
             "#C9A227", "#64748B", "#8E7CC3", "#D9822B"][i % 8]) for i, k in enumerate(parts)]
    if isinstance(colors, dict):
        colors = [colors[k] for k in parts]
    s = [_frame(w, h)]
    a0 = -math.pi / 2
    for i, (k, v) in enumerate(parts.items()):
        frac = v / total; a1 = a0 + frac * 2 * math.pi
        x0, y0 = cx + r*math.cos(a0), cy + r*math.sin(a0)
        x1, y1 = cx + r*math.cos(a1), cy + r*math.sin(a1)
        xi0, yi0 = cx + rin*math.cos(a1), cy + rin*math.sin(a1)
        xi1, yi1 = cx + rin*math.cos(a0), cy + rin*math.sin(a0)
        large = 1 if frac > 0.5 else 0
        s.append(f'<path d="M{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 {large} 1 {x1:.1f},{y1:.1f} '
                 f'L{xi0:.1f},{yi0:.1f} A{rin:.1f},{rin:.1f} 0 {large} 0 {xi1:.1f},{yi1:.1f} Z" fill="{colors[i]}"/>')
        a0 = a1
    if center:
        s.append(_t(cx, cy - 2, center, size=15, col=INK, weight=800))
    if csub:
        s.append(_t(cx, cy + 13, csub, size=8.5, col=MUTE))
    ly = h*0.5 - len(parts)*9
    lx = w * 0.64
    for i, (k, v) in enumerate(parts.items()):
        yy = ly + i * 18
        s.append(f'<rect x="{lx}" y="{yy-8}" width="9" height="9" rx="2" fill="{colors[i]}"/>')
        s.append(_t(lx + 13, yy, f"{k}", size=8.5, col=INK, anchor="start", weight=600))
        s.append(_t(lx + 13, yy + 10, pct(v/total), size=8, col=MUTE, anchor="start"))
    s.append("</svg>")
    return "".join(s)


def sparkline(vals, labels, color=NEU, w=300, h=215, fmt="pct"):
    L, R, T, B = 26, 26, 26, 22
    pw, ph = w - L - R, h - T - B
    vmax = max(vals); vmin = min(vals); rng = (vmax - vmin) or 1
    n = len(vals); pts = []
    for i, v in enumerate(vals):
        x = L + (pw * (i/(n-1) if n > 1 else 0.5))
        y = T + (vmax - v)/rng*ph
        pts.append((x, y))
    s = [_frame(w, h)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.6"/>')
    for i, (x, y) in enumerate(pts):
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{color}"/>')
        s.append(_t(x, h - 7, labels[i], size=8.5, col=MUTE))
    s.append(_t(pts[0][0]-3, pts[0][1]-8, _flabel(vals[0], fmt), size=9, col=MUTE, anchor="middle"))
    s.append(_t(pts[-1][0]+3, pts[-1][1]-8, _flabel(vals[-1], fmt), size=10, col=color, anchor="middle", weight=800))
    s.append("</svg>")
    return "".join(s)
