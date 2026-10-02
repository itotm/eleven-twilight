#!/usr/bin/env python3
"""Generator for the ElevenTwilightColoredToolbars icon theme.

Draws the Windows 11 (Fluent) style colored action icons on two native grids,
16 and 24 px, and assembles the theme tree following the freedesktop.org Icon
Theme Specification 0.13. The theme is an overlay: it only holds the redrawn
icons, everything else is inherited from ElevenTwilight.

Usage: python3 tools/build.py [--install]
"""
import configparser
import math
import os
import shutil
import sys
from pathlib import Path

try:
    import cairo
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
except (ImportError, ValueError):
    Rsvg = None

ROOT = Path(__file__).resolve().parent.parent
NAME = "ElevenTwilightColoredToolbars"
THEME = ROOT / "src" / NAME
VERSIONS = ROOT / "VERSIONS"

# --- Fluent palette ---------------------------------------------------------
BLUE = "#0078d4"
BLUE_L = "#4ca5e8"
BLUE_P = "#cfe7fa"
BLUE_F = "#eaf3fb"
PAPER = "#ffffff"
EDGE = "#8a8886"
LINE = "#c8c6c4"
AMBER = "#ffc233"
AMBER_D = "#e0a200"
RED = "#c42b1c"
RED_L = "#ef6b57"
RED_D = "#d1503c"
GREEN = "#107c10"
GRAY = "#605e5c"
GRAY_L = "#a19f9d"
BROWN = "#c58e4a"

# --- primitives --------------------------------------------------------------


def n(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def P(d, fill="none", stroke=None, w=1.5, cap="round", extra=""):
    s = f'<path d="{d}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{n(w)}"'
        s += f' stroke-linecap="{cap}" stroke-linejoin="round"'
    if extra:
        s += " " + extra
    return s + "/>"


def R(x, y, w, h, fill, rx=0, stroke=None, sw=1, extra=""):
    s = f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"'
    if rx:
        s += f' rx="{n(rx)}"'
    s += f' fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}"'
    if extra:
        s += " " + extra
    return s + "/>"


def C(cx, cy, r, fill="none", stroke=None, sw=1, extra=""):
    s = f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{n(sw)}"'
    if extra:
        s += " " + extra
    return s + "/>"


def G(body, transform):
    return f'<g transform="{transform}">{body}</g>'


def gear(cx, cy, ro, ri, teeth=8, fill=BLUE):
    """Cog outline generated analytically, so it stays clean at any scale."""
    pts = []
    step = math.pi / teeth
    for i in range(teeth):
        a0 = 2 * step * i
        for r, a in ((ro, a0 - step * 0.36), (ro, a0 + step * 0.36),
                     (ri, a0 + step * 0.74), (ri, a0 + step * 1.26)):
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d = "M" + " ".join(f"{n(x)} {n(y)}" for x, y in pts) + "Z"
    return f'<path d="{d}" fill="{fill}"/>'


def star(cx, cy, r, fill=AMBER, points=5, inner=0.46):
    pts = []
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * inner
        a = -math.pi / 2 + i * math.pi / points
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    d = "M" + " ".join(f"{n(x)} {n(y)}" for x, y in pts) + "Z"
    return f'<path d="{d}" fill="{fill}" stroke="{fill}" stroke-width="0.6"' \
           ' stroke-linejoin="round"/>'


def magnifier(cx, cy, r, w, color=BLUE, lens=BLUE_P):
    out = ""
    if lens != "none":
        out += C(cx, cy, r, lens)
    out += C(cx, cy, r, "none", color, w)
    k = 0.7071
    out += P(f"M{n(cx + r * k)} {n(cy + r * k)}"
             f"L{n(cx + (r + w * 1.9) * k)} {n(cy + (r + w * 1.9) * k)}",
             stroke=color, w=w * 1.25)
    return out


# --- badge glyphs ------------------------------------------------------
# shared signature: (cx, cy, a, t, bg) -> white markup on top of the colored disc


def g_plus(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx - a)} {n(cy)}h{n(2 * a)}M{n(cx)} {n(cy - a)}v{n(2 * a)}",
             stroke=PAPER, w=t)


def g_minus(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx - a)} {n(cy)}h{n(2 * a)}", stroke=PAPER, w=t)


def g_x(cx, cy, a, t, bg=BLUE):
    b = a * 0.78
    return P(f"M{n(cx - b)} {n(cy - b)}L{n(cx + b)} {n(cy + b)}"
             f"M{n(cx + b)} {n(cy - b)}L{n(cx - b)} {n(cy + b)}",
             stroke=PAPER, w=t)


def g_check(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx - a * 0.85)} {n(cy + a * 0.05)}"
             f"l{n(a * 0.6)} {n(a * 0.68)} {n(a * 1.15)} {n(-a * 1.3)}",
             stroke=PAPER, w=t)


def g_arrow_down(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx)} {n(cy - a)}v{n(2 * a)}"
             f"M{n(cx - a * 0.72)} {n(cy + a * 0.32)}L{n(cx)} {n(cy + a)}"
             f"l{n(a * 0.72)} {n(-a * 0.68)}", stroke=PAPER, w=t)


def g_arrow_up(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx)} {n(cy + a)}v{n(-2 * a)}"
             f"M{n(cx - a * 0.72)} {n(cy - a * 0.32)}L{n(cx)} {n(cy - a)}"
             f"l{n(a * 0.72)} {n(a * 0.68)}", stroke=PAPER, w=t)


def g_arrow_right(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx - a)} {n(cy)}h{n(2 * a)}"
             f"M{n(cx + a * 0.32)} {n(cy - a * 0.72)}L{n(cx + a)} {n(cy)}"
             f"l{n(-a * 0.68)} {n(a * 0.72)}", stroke=PAPER, w=t)


def g_arrow_left(cx, cy, a, t, bg=BLUE):
    return P(f"M{n(cx + a)} {n(cy)}h{n(-2 * a)}"
             f"M{n(cx - a * 0.32)} {n(cy - a * 0.72)}L{n(cx - a)} {n(cy)}"
             f"l{n(a * 0.68)} {n(a * 0.72)}", stroke=PAPER, w=t)


def g_pencil(cx, cy, a, t, bg=BLUE):
    d = (f"M{n(cx + a * 0.52)} {n(cy - a * 1.15)}"
         f"l{n(a * 0.62)} {n(a * 0.62)}"
         f"l{n(-a * 0.3)} {n(a * 0.3)}"
         f"l{n(-a * 0.62)} {n(-a * 0.62)}Z"
         f"M{n(cx + a * 0.12)} {n(cy - a * 0.75)}"
         f"l{n(a * 0.62)} {n(a * 0.62)}"
         f"l{n(-a * 1.15)} {n(a * 1.15)}"
         f"l{n(-a * 0.82)} {n(a * 0.2)}"
         f"l{n(a * 0.2)} {n(-a * 0.82)}Z")
    return P(d, fill=PAPER)


def g_gear(cx, cy, a, t, bg=BLUE):
    return gear(cx, cy, a * 1.15, a * 0.84, 8, PAPER) + C(cx, cy, a * 0.42, bg)


def g_magnifier(cx, cy, a, t, bg=BLUE):
    return magnifier(cx - a * 0.18, cy - a * 0.18, a * 0.72, t * 0.85,
                     color=PAPER, lens="none")


def g_undo(cx, cy, a, t, bg=BLUE):
    r = a * 0.8
    return (P(f"M{n(cx - a * 0.15)} {n(cy - r)}"
              f"a{n(r)} {n(r)} 0 1 1 {n(-r * 0.9)} {n(r * 1.75)}",
              stroke=PAPER, w=t) +
            P(f"M{n(cx - a * 0.95)} {n(cy - a * 1.1)}"
              f"L{n(cx - a * 0.1)} {n(cy - a * 0.78)}"
              f"L{n(cx - a * 0.62)} {n(cy - a * 0.02)}", stroke=PAPER, w=t))


def g_share(cx, cy, a, t, bg=BLUE):
    r = a * 0.42
    return (P(f"M{n(cx - a * 0.7)} {n(cy)}L{n(cx + a * 0.7)} {n(cy - a * 0.85)}"
              f"M{n(cx - a * 0.7)} {n(cy)}L{n(cx + a * 0.7)} {n(cy + a * 0.85)}",
              stroke=PAPER, w=t * 0.62) +
            C(cx + a * 0.72, cy - a * 0.85, r, PAPER) +
            C(cx + a * 0.72, cy + a * 0.85, r, PAPER) +
            C(cx - a * 0.78, cy, r, PAPER))


# --- shared parts --------------------------------------------------------

# Ink size every icon is normalized to (longer side, in grid units). It keeps
# the median size of the first release, whose icons sat next to the
# ElevenTwilight ones at 16 px (median ink 14.0 there): measured with librsvg,
# filling the whole grid made them clearly larger than the base theme.
TARGET = {24: 19.4, 16: 13.8}

GEO = {
    24: dict(bx=17.6, by=17.6, ring=6.1, disc=5.1, a=3.0, t=1.9),
    16: dict(bx=11.4, by=11.4, ring=4.5, disc=3.7, a=2.05, t=1.4),
}


def badge(g, color, glyph):
    q = GEO[g]
    return (C(q["bx"], q["by"], q["ring"], PAPER) +
            C(q["bx"], q["by"], q["disc"], color) +
            glyph(q["bx"], q["by"], q["a"], q["t"], color))


def page(g, lines=True):
    if g == 24:
        out = (P("M3.5 3.5a2 2 0 0 1 2-2h9L20.5 7.5V20.5a2 2 0 0 1-2 2h-13"
                 "a2 2 0 0 1-2-2Z", fill=PAPER, stroke=EDGE, w=1.3) +
               P("M14.5 1.5 20.5 7.5h-4.8a1.2 1.2 0 0 1-1.2-1.2Z", fill=BLUE_P))
        if lines:
            out += P("M7 11h10M7 14.5h10M7 18h6", stroke=LINE, w=1.5)
        return out
    out = (P("M2 2.4A1.4 1.4 0 0 1 3.4 1h6L14 5.6V13.6A1.4 1.4 0 0 1 12.6 15H3.4"
             "A1.4 1.4 0 0 1 2 13.6Z", fill=PAPER, stroke=EDGE, w=1) +
           P("M9.4 1 14 5.6h-3.4a1.2 1.2 0 0 1-1.2-1.2Z", fill=BLUE_P))
    if lines:
        out += P("M4.6 8h6.8M4.6 10.6h6.8", stroke=LINE, w=1.2)
    return out


def folder(g):
    if g == 24:
        return (P("M1.5 5.5a2 2 0 0 1 2-2h6l2.2 2.2h8.8a2 2 0 0 1 2 2V19"
                  "a2 2 0 0 1-2 2h-17a2 2 0 0 1-2-2Z", fill=AMBER_D) +
                P("M1.5 10.4h21V19a2 2 0 0 1-2 2h-17a2 2 0 0 1-2-2Z", fill=AMBER))
    return (P("M1 4a1.4 1.4 0 0 1 1.4-1.4h3.8L7.6 4h6A1.4 1.4 0 0 1 15 5.4v7.2"
              "A1.4 1.4 0 0 1 13.6 14H2.4A1.4 1.4 0 0 1 1 12.6Z", fill=AMBER_D) +
            P("M1 7.2h14v5.4A1.4 1.4 0 0 1 13.6 14H2.4A1.4 1.4 0 0 1 1 12.6Z",
              fill=AMBER))


def floppy(g):
    if g == 24:
        return (R(1.5, 1.5, 21, 21, BLUE, rx=2.4) +
                R(7, 1.5, 10, 8.4, PAPER, rx=0.7) +
                R(12.6, 3, 2.6, 5.4, BLUE, rx=0.4) +
                R(5.4, 13.6, 13.2, 8.9, PAPER, rx=1.2))
    return (R(1, 1, 14, 14, BLUE, rx=1.8) +
            R(4.8, 1, 6.4, 5.6, PAPER, rx=0.5) +
            R(8.4, 2, 1.8, 3.6, BLUE, rx=0.3) +
            R(3.6, 9.6, 8.8, 5.4, PAPER, rx=0.8))


def envelope(g):
    if g == 24:
        return (R(1.2, 4.4, 21.6, 15.2, PAPER, rx=2.2, stroke=BLUE, sw=1.5) +
                P("M2 5.6 12 13l10-7.4", stroke=BLUE, w=1.5))
    return (R(1, 3, 14, 10, PAPER, rx=1.5, stroke=BLUE, sw=1.25) +
            P("M1.6 3.8 8 8.8l6.4-5", stroke=BLUE, w=1.25))


def printer(g):
    if g == 24:
        return (R(5, 1, 14, 7.6, PAPER, rx=1, stroke=EDGE, sw=1.2) +
                R(1.5, 7.6, 21, 9, BLUE, rx=2.2) +
                C(19, 10.6, 1, "#a6e6a1") +
                R(5, 13, 14, 9.5, PAPER, rx=1, stroke=EDGE, sw=1.2))
    return (R(3.4, 0.8, 9.2, 4.8, PAPER, rx=0.7, stroke=EDGE, sw=0.9) +
            R(1, 5.2, 14, 6, BLUE, rx=1.4) +
            C(12.8, 7.2, 0.7, "#a6e6a1") +
            R(3.4, 8.8, 9.2, 6.2, PAPER, rx=0.7, stroke=EDGE, sw=0.9))


def archive_box(g):
    if g == 24:
        return (R(1.5, 5.6, 21, 16.4, AMBER, rx=2.2) +
                R(1.5, 2.6, 21, 5, AMBER_D, rx=1.8) +
                R(10.4, 7.6, 3.2, 4, AMBER_D, rx=0.6))
    return (R(1, 3.8, 14, 11, AMBER, rx=1.5) +
            R(1, 1.8, 14, 3.6, AMBER_D, rx=1.2) +
            R(6.8, 5.2, 2.4, 2.8, AMBER_D, rx=0.5))


def window(g):
    if g == 24:
        return (R(1.5, 2.5, 21, 19, PAPER, rx=2.2, stroke=BLUE, sw=1.5) +
                P("M1.5 4.7a2.2 2.2 0 0 1 2.2-2.2h16.6a2.2 2.2 0 0 1 2.2 2.2V7.6"
                  "h-21Z", fill=BLUE))
    return (R(1, 1.6, 14, 12.8, PAPER, rx=1.5, stroke=BLUE, sw=1.25) +
            P("M1 3.1a1.5 1.5 0 0 1 1.5-1.5h11a1.5 1.5 0 0 1 1.5 1.5V5H1Z",
              fill=BLUE))


# --- icon registry ---------------------------------------------------------

ICONS = {}


def icon(name):
    def deco(fn):
        ICONS[name] = fn
        return fn
    return deco


# File group ----------------------------------------------------------------

@icon("document-new")
def _(g):
    return page(g) + badge(g, GREEN, g_plus)


@icon("document-open")
def _(g):
    if g == 24:
        return (P("M2 6a2 2 0 0 1 2-2h5.2l2 2H19a2 2 0 0 1 2 2v2.4H6.6"
                  "a2 2 0 0 0-1.9 1.4L2 20Z", fill=AMBER_D) +
                P("M2.8 20.4 5.6 11.9A1.6 1.6 0 0 1 7.1 10.8H22l-2.8 8.5"
                  "a1.6 1.6 0 0 1-1.5 1.1Z", fill=AMBER))
    return (P("M1.5 4.4a1.4 1.4 0 0 1 1.4-1.4h3.4l1.4 1.4H13a1.4 1.4 0 0 1 1.4 1.4"
              "v1.6H4.6a1.4 1.4 0 0 0-1.3 1L1.5 13.6Z", fill=AMBER_D) +
            P("M2 13.8 3.8 8.3a1.1 1.1 0 0 1 1.1-.8h9.9l-1.8 5.5a1.1 1.1 0 0 1-1.1.8Z",
              fill=AMBER))


@icon("document-save")
def _(g):
    return floppy(g)


@icon("document-save-as")
def _(g):
    return floppy(g) + badge(g, BLUE, g_pencil)


@icon("document-save-all")
def _(g):
    if g == 24:
        return (R(7, 1.5, 15.5, 15.5, BLUE_L, rx=2) +
                R(11.5, 1.5, 6.5, 5.5, PAPER, rx=0.6) +
                G(floppy(24), "translate(1.5 5.5) scale(0.79)"))
    return (R(4.5, 1, 10.5, 10.5, BLUE_L, rx=1.4) +
            R(7.4, 1, 4.4, 3.8, PAPER, rx=0.4) +
            G(floppy(16), "translate(0.8 3.6) scale(0.78)"))


@icon("document-print")
def _(g):
    return printer(g)


@icon("document-print-preview")
def _(g):
    return printer(g) + badge(g, BLUE, g_magnifier)


@icon("document-properties")
def _(g):
    return page(g) + badge(g, BLUE, g_gear)


@icon("document-close")
def _(g):
    return page(g) + badge(g, RED, g_x)


@icon("document-import")
def _(g):
    return page(g) + badge(g, BLUE, g_arrow_down)


@icon("document-export")
def _(g):
    return page(g) + badge(g, BLUE, g_arrow_up)


@icon("document-share")
def _(g):
    return page(g) + badge(g, BLUE, g_share)


@icon("document-revert")
def _(g):
    return page(g) + badge(g, BLUE, g_undo)


@icon("document-edit")
def _(g):
    return page(g) + badge(g, BLUE, g_pencil)


# Edit group ------------------------------------------------------------

@icon("edit-cut")
def _(g):
    if g == 24:
        return (P("M7.6 3.2 15.6 16.6", stroke=GRAY, w=2) +
                P("M16.4 3.2 8.4 16.6", stroke=GRAY_L, w=2) +
                C(7.4, 18.6, 2.9, "none", BLUE, 1.9) +
                C(16.6, 18.6, 2.9, "none", BLUE, 1.9))
    return (P("M4.8 1.6 10.4 10.4", stroke=GRAY, w=1.5) +
            P("M11.2 1.6 5.6 10.4", stroke=GRAY_L, w=1.5) +
            C(4.5, 12.4, 2.1, "none", BLUE, 1.4) +
            C(11.5, 12.4, 2.1, "none", BLUE, 1.4))


@icon("edit-copy")
def _(g):
    if g == 24:
        return (R(3.7, 1.7, 12.6, 16.6, BLUE_F, rx=2, stroke=BLUE, sw=1.4) +
                R(7.7, 5.7, 12.6, 16.6, PAPER, rx=2, stroke=BLUE, sw=1.4))
    return (R(2.1, 1.1, 8.8, 11.4, BLUE_F, rx=1.5, stroke=BLUE, sw=1.1) +
            R(5.1, 3.9, 8.8, 11.4, PAPER, rx=1.5, stroke=BLUE, sw=1.1))


@icon("edit-paste")
def _(g):
    if g == 24:
        return (R(3.5, 3, 17, 19, BROWN, rx=2.2) +
                R(6.2, 7, 11.6, 12.4, PAPER, rx=1) +
                R(8.6, 1.4, 6.8, 4.4, GRAY, rx=1.4) +
                R(7.2, 3.6, 9.6, 3.2, "#8a8886", rx=1.1))
    return (R(2.2, 2, 11.6, 13, BROWN, rx=1.5) +
            R(4, 4.6, 8, 8.4, PAPER, rx=0.7) +
            R(5.8, 0.9, 4.4, 2.9, GRAY, rx=0.9) +
            R(4.8, 2.4, 6.4, 2.2, "#8a8886", rx=0.8))


@icon("edit-delete")
def _(g):
    if g == 24:
        return (R(9.4, 2.2, 5.2, 2.8, RED, rx=1) +
                R(3.6, 4.8, 16.8, 2.6, RED, rx=1.3) +
                P("M5.6 8.2h12.8l-1 12.1a2 2 0 0 1-2 1.7H8.6a2 2 0 0 1-2-1.7Z",
                  fill=LINE) +
                P("M9.6 11.4v7M12 11.4v7M14.4 11.4v7", stroke=PAPER, w=1.3))
    return (R(6, 1.4, 4, 2, RED, rx=0.8) +
            R(2.2, 3.2, 11.6, 2, RED, rx=1) +
            P("M3.6 5.9h8.8l-.8 8a1.4 1.4 0 0 1-1.4 1.3H5.8a1.4 1.4 0 0 1-1.4-1.3Z",
              fill=LINE) +
            P("M6.4 8.2v4.6M9.6 8.2v4.6", stroke=PAPER, w=1.1))


@icon("edit-undo")
def _(g):
    if g == 24:
        return (P("M6 9h8.6a5.6 5.6 0 0 1 0 11.2H9", stroke=BLUE, w=2.4) +
                P("M10.2 4.4 5.2 9l5 4.6", stroke=BLUE, w=2.4))
    return (P("M4 6h5.8a3.6 3.6 0 0 1 0 7.2H6", stroke=BLUE, w=1.7) +
            P("M6.8 3 3.4 6l3.4 3", stroke=BLUE, w=1.7))


@icon("edit-redo")
def _(g):
    if g == 24:
        return (P("M18 9H9.4a5.6 5.6 0 0 0 0 11.2H15", stroke=GREEN, w=2.4) +
                P("M13.8 4.4 18.8 9l-5 4.6", stroke=GREEN, w=2.4))
    return (P("M12 6H6.2a3.6 3.6 0 0 0 0 7.2H10", stroke=GREEN, w=1.7) +
            P("M9.2 3 12.6 6l-3.4 3", stroke=GREEN, w=1.7))


@icon("edit-rename")
def _(g):
    if g == 24:
        return (R(2.2, 5.5, 15.6, 12, BLUE_F, rx=2, stroke=BLUE, sw=1.3) +
                P("M6.4 8.4v6.2M4.9 8.4h3M4.9 14.6h3", stroke=BLUE, w=1.3) +
                P("M10.4 11h5M10.4 14h3.4", stroke=GRAY_L, w=1.3) +
                badge(24, BLUE, g_pencil))
    return (R(1.4, 3.4, 10.4, 8, BLUE_F, rx=1.4, stroke=BLUE, sw=1.1) +
            P("M4.4 5.2v4.4M3.4 5.2h2M3.4 9.6h2", stroke=BLUE, w=1.1) +
            P("M7 6.4h3M7 8.6h2", stroke=GRAY_L, w=1.1) +
            badge(16, BLUE, g_pencil))


@icon("edit-find")
def _(g):
    if g == 24:
        return page(g, lines=False) + P("M8 9h8M8 12h5", stroke=LINE, w=1.4) + \
            C(15.6, 15.6, 6.6, PAPER) + magnifier(15.4, 15.4, 4.9, 1.9)
    return page(g, lines=False) + P("M5.4 6.4h5.2M5.4 8.6h3.4", stroke=LINE, w=1.2) + \
        C(10.6, 10.6, 4.9, PAPER) + magnifier(10.5, 10.5, 3.5, 1.4)


@icon("edit-find-replace")
def _(g):
    if g == 24:
        return (magnifier(9.8, 9.8, 6.4, 2.2) +
                P("M13.4 17.6h6.4l-1.8-1.9M20.2 20.8h-6.4l1.8 1.9",
                  stroke=GREEN, w=1.6))
    return (magnifier(6.6, 6.6, 4.3, 1.6) +
            P("M9 11.4h4.4l-1.2-1.3M13.8 13.6H9.4l1.2 1.3", stroke=GREEN, w=1.3))


@icon("edit-select-all")
def _(g):
    if g == 24:
        return (R(2.6, 2.6, 18.8, 18.8, BLUE_F, rx=2, stroke=BLUE, sw=1.6,
                  extra='stroke-dasharray="4 3"') +
                P("M7 9h10M7 12.5h10M7 16h6", stroke=GRAY_L, w=1.6))
    return (R(1.6, 1.6, 12.8, 12.8, BLUE_F, rx=1.4, stroke=BLUE, sw=1.3,
              extra='stroke-dasharray="3 2.2"') +
            P("M4.5 6h7M4.5 8.4h7M4.5 10.8h4", stroke=GRAY_L, w=1.3))


@icon("edit-clear")
def _(g):
    if g == 24:
        body = (R(3.4, 8.4, 17.2, 7.2, RED_L, rx=1.6) +
                R(14.2, 8.4, 6.4, 7.2, RED_D, rx=1.6))
        return G(body, "rotate(-45 12 12)") + P("M3 21h18", stroke=GRAY_L, w=2)
    body = (R(2, 5.5, 12, 5, RED_L, rx=1.1) +
            R(9.6, 5.5, 4.4, 5, RED_D, rx=1.1))
    return G(body, "rotate(-45 8 8)") + P("M2 14h12", stroke=GRAY_L, w=1.5)


# Folders and archives group --------------------------------------------------

@icon("folder-new")
def _(g):
    return folder(g) + badge(g, GREEN, g_plus)


@icon("archive-insert")
def _(g):
    return archive_box(g) + badge(g, BLUE, g_arrow_down)


@icon("archive-extract")
def _(g):
    return archive_box(g) + badge(g, BLUE, g_arrow_up)


# View and zoom group --------------------------------------------------------

@icon("zoom-in")
def _(g):
    if g == 24:
        return magnifier(10.4, 10.4, 6.8, 2.2) + \
            P("M7.2 10.4h6.4M10.4 7.2v6.4", stroke=BLUE, w=2)
    return magnifier(6.9, 6.9, 4.5, 1.6) + \
        P("M4.8 6.9h4.2M6.9 4.8v4.2", stroke=BLUE, w=1.5)


@icon("zoom-out")
def _(g):
    if g == 24:
        return magnifier(10.4, 10.4, 6.8, 2.2) + P("M7.2 10.4h6.4", stroke=BLUE, w=2)
    return magnifier(6.9, 6.9, 4.5, 1.6) + P("M4.8 6.9h4.2", stroke=BLUE, w=1.5)


@icon("zoom-original")
def _(g):
    if g == 24:
        return magnifier(10.4, 10.4, 6.8, 2.2) + R(7.6, 7.6, 5.6, 5.6, BLUE, rx=1)
    return magnifier(6.9, 6.9, 4.5, 1.6) + R(5.1, 5.1, 3.6, 3.6, BLUE, rx=0.7)


@icon("zoom-fit-best")
def _(g):
    if g == 24:
        return (R(2.6, 4.6, 18.8, 14.8, BLUE_F, rx=2, stroke=BLUE, sw=1.4) +
                P("M7 8.6V7.4h1.6M17 8.6V7.4h-1.6M7 15.4v1.2h1.6M17 15.4v1.2h-1.6",
                  stroke=BLUE, w=1.8) +
                P("M10.6 12h2.8", stroke=BLUE, w=1.8))
    return (R(1.5, 3, 13, 10, BLUE_F, rx=1.4, stroke=BLUE, sw=1.2) +
            P("M4.4 6V5.2h1.2M11.6 6V5.2h-1.2M4.4 10v.8h1.2M11.6 10v.8h-1.2",
              stroke=BLUE, w=1.3) +
            P("M7.2 8h1.6", stroke=BLUE, w=1.3))


@icon("view-refresh")
def _(g):
    if g == 24:
        return (P("M20 12a8 8 0 1 1-2.4-5.7", stroke=BLUE, w=2.4) +
                P("M18.4 2.8v4.6h-4.6", stroke=BLUE, w=2.4))
    return (P("M13.4 8a5.4 5.4 0 1 1-1.6-3.8", stroke=BLUE, w=1.7) +
            P("M12.4 1.8v3.1h-3.1", stroke=BLUE, w=1.7))


@icon("view-filter")
def _(g):
    if g == 24:
        return P("M3 5A2 2 0 0 1 5 3h14a2 2 0 0 1 1.5 3.3l-6 7V20a1 1 0 0 1-1.5.9"
                 "l-3-1.8a1 1 0 0 1-.5-.9v-4.9l-6-7A2 2 0 0 1 3 5Z", fill=BLUE)
    return P("M2 3.4A1.4 1.4 0 0 1 3.4 2h9.2A1.4 1.4 0 0 1 13.7 4.3L9.6 8.9V13.4"
             "a.7.7 0 0 1-1.05.6l-2-1.2a.7.7 0 0 1-.35-.6V8.9L2.3 4.3A1.4 1.4 0 0 1 2 3.4Z",
             fill=BLUE)


@icon("view-sort-ascending")
def _(g):
    if g == 24:
        return (P("M6 20.5V4.5M2.6 8 6 4.5 9.4 8", stroke=BLUE, w=2.2) +
                R(12, 4.5, 4.4, 2.2, EDGE, rx=1.1) +
                R(12, 9, 6.6, 2.2, EDGE, rx=1.1) +
                R(12, 13.5, 8.8, 2.2, EDGE, rx=1.1) +
                R(12, 18, 11, 2.2, EDGE, rx=1.1))
    return (P("M4 14V2.6M2 4.6 4 2.6 6 4.6", stroke=BLUE, w=1.6) +
            R(8, 2.8, 2.8, 1.6, EDGE, rx=0.8) +
            R(8, 6, 4.2, 1.6, EDGE, rx=0.8) +
            R(8, 9.2, 5.6, 1.6, EDGE, rx=0.8) +
            R(8, 12.4, 7, 1.6, EDGE, rx=0.8))


@icon("view-sort-descending")
def _(g):
    if g == 24:
        return (P("M6 4.5v16M2.6 17 6 20.5 9.4 17", stroke=BLUE, w=2.2) +
                R(12, 4.5, 11, 2.2, EDGE, rx=1.1) +
                R(12, 9, 8.8, 2.2, EDGE, rx=1.1) +
                R(12, 13.5, 6.6, 2.2, EDGE, rx=1.1) +
                R(12, 18, 4.4, 2.2, EDGE, rx=1.1))
    return (P("M4 2.6V14M2 12 4 14l2-2", stroke=BLUE, w=1.6) +
            R(8, 2.8, 7, 1.6, EDGE, rx=0.8) +
            R(8, 6, 5.6, 1.6, EDGE, rx=0.8) +
            R(8, 9.2, 4.2, 1.6, EDGE, rx=0.8) +
            R(8, 12.4, 2.8, 1.6, EDGE, rx=0.8))


@icon("view-list-details")
def _(g):
    if g == 24:
        out = ""
        for y in (4.4, 10.4, 16.4):
            out += R(2.6, y, 3.4, 3.4, BLUE, rx=0.9)
            out += R(8, y + 0.7, 13.4, 2, EDGE, rx=1)
        return out
    out = ""
    for y in (2.6, 6.9, 11.2):
        out += R(1.5, y, 2.4, 2.4, BLUE, rx=0.6)
        out += R(5.2, y + 0.5, 9.3, 1.4, EDGE, rx=0.7)
    return out


@icon("view-list-icons")
def _(g):
    if g == 24:
        return (R(2.8, 2.8, 8.4, 8.4, BLUE, rx=1.6) +
                R(12.8, 2.8, 8.4, 8.4, GREEN, rx=1.6) +
                R(2.8, 12.8, 8.4, 8.4, AMBER, rx=1.6) +
                R(12.8, 12.8, 8.4, 8.4, RED, rx=1.6))
    return (R(1.5, 1.5, 5.8, 5.8, BLUE, rx=1) +
            R(8.7, 1.5, 5.8, 5.8, GREEN, rx=1) +
            R(1.5, 8.7, 5.8, 5.8, AMBER, rx=1) +
            R(8.7, 8.7, 5.8, 5.8, RED, rx=1))


@icon("view-fullscreen")
def _(g):
    if g == 24:
        return P("M3 9V4a1 1 0 0 1 1-1h5M15 3h5a1 1 0 0 1 1 1v5M21 15v5"
                 "a1 1 0 0 1-1 1h-5M9 21H4a1 1 0 0 1-1-1v-5", stroke=BLUE, w=2.2)
    return P("M2 6V3a1 1 0 0 1 1-1h3M10 2h3a1 1 0 0 1 1 1v3M14 10v3"
             "a1 1 0 0 1-1 1h-3M6 14H3a1 1 0 0 1-1-1v-3", stroke=BLUE, w=1.6)


# Navigation group ---------------------------------------------------------

@icon("go-previous")
def _(g):
    if g == 24:
        return P("M20 12H7M13 6l-6 6 6 6", stroke=BLUE, w=2.4)
    return P("M13.5 8h-9M8 4 4 8l4 4", stroke=BLUE, w=1.8)


@icon("go-next")
def _(g):
    if g == 24:
        return P("M4 12h13M11 6l6 6-6 6", stroke=BLUE, w=2.4)
    return P("M2.5 8h9M8 4l4 4-4 4", stroke=BLUE, w=1.8)


@icon("go-up")
def _(g):
    if g == 24:
        return P("M12 20V7M6 13l6-6 6 6", stroke=BLUE, w=2.4)
    return P("M8 13.5v-9M4 8.5l4-4 4 4", stroke=BLUE, w=1.8)


@icon("go-home")
def _(g):
    if g == 24:
        return (P("M2.6 11.6 12 3.4l9.4 8.2", stroke=BLUE, w=2.4) +
                P("M5 11.4v8.6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8.6",
                  fill=BLUE_F, stroke=BLUE, w=1.6) +
                R(10, 15, 4, 6, BLUE, rx=0.6))
    return (P("M1.6 7.6 8 2.2l6.4 5.4", stroke=BLUE, w=1.7) +
            P("M3.4 7.4v6.1a.8.8 0 0 0 .8.8h7.6a.8.8 0 0 0 .8-.8V7.4",
              fill=BLUE_F, stroke=BLUE, w=1.2) +
            R(6.6, 10, 2.8, 4.3, BLUE, rx=0.4))


@icon("go-jump")
def _(g):
    if g == 24:
        return (P("M2.5 12h12M10.5 6.5 16 12l-5.5 5.5", stroke=BLUE, w=2.4) +
                R(18.4, 4, 2.6, 16, GRAY, rx=1.3))
    return (P("M1.5 8h7.5M7 5l3 3-3 3", stroke=BLUE, w=1.8) +
            R(12, 2.6, 1.8, 10.8, GRAY, rx=0.9))


# Lists group ---------------------------------------------------------------

@icon("list-add")
def _(g):
    if g == 24:
        return C(12, 12, 9.6, GREEN) + P("M7.4 12h9.2M12 7.4v9.2", stroke=PAPER, w=2.4)
    return C(8, 8, 6.4, GREEN) + P("M4.9 8h6.2M8 4.9v6.2", stroke=PAPER, w=1.8)


@icon("list-remove")
def _(g):
    if g == 24:
        return C(12, 12, 9.6, RED) + P("M7.4 12h9.2", stroke=PAPER, w=2.4)
    return C(8, 8, 6.4, RED) + P("M4.9 8h6.2", stroke=PAPER, w=1.8)


# Mail group ---------------------------------------------------------------

@icon("mail-send")
def _(g):
    if g == 24:
        return (P("M22 2.5 2 10.4l7.6 2.9 2.9 7.7Z", fill=BLUE) +
                P("M22 2.5 9.6 13.3l2.9 7.7Z", fill=BLUE_L))
    return (P("M14.7 1.4 1.3 6.7l5.1 1.9 1.9 5.2Z", fill=BLUE) +
            P("M14.7 1.4 6.4 8.6l1.9 5.2Z", fill=BLUE_L))


@icon("mail-message-new")
def _(g):
    return envelope(g) + badge(g, GREEN, g_plus)


@icon("mail-forward")
def _(g):
    return envelope(g) + badge(g, BLUE, g_arrow_right)


@icon("mail-reply-sender")
def _(g):
    return envelope(g) + badge(g, BLUE, g_arrow_left)


# Media group ---------------------------------------------------------------

@icon("media-playback-start")
def _(g):
    if g == 24:
        return P("M8 5.4 18.6 12 8 18.6Z", fill=GREEN, stroke=GREEN, w=2)
    return P("M5 3.4 12.4 8 5 12.6Z", fill=GREEN, stroke=GREEN, w=1.4)


@icon("media-playback-pause")
def _(g):
    if g == 24:
        return R(6.4, 4.6, 4.2, 14.8, BLUE, rx=1.3) + R(13.4, 4.6, 4.2, 14.8, BLUE, rx=1.3)
    return R(3.8, 2.8, 3, 10.4, BLUE, rx=0.9) + R(9.2, 2.8, 3, 10.4, BLUE, rx=0.9)


@icon("media-playback-stop")
def _(g):
    if g == 24:
        return R(5.2, 5.2, 13.6, 13.6, RED, rx=2.2)
    return R(3.2, 3.2, 9.6, 9.6, RED, rx=1.5)


# Insert group -----------------------------------------------------------

@icon("insert-image")
def _(g):
    if g == 24:
        return (R(2.6, 4.4, 18.8, 15.2, BLUE_F, rx=2, stroke=BLUE, sw=1.4) +
                C(8, 9.6, 2.1, AMBER) +
                P("M3.4 19 9.4 12l4.6 5.4 2.6-2.6 4.6 4.2Z", fill=GREEN))
    return (R(1.5, 2.9, 13, 10.2, BLUE_F, rx=1.4, stroke=BLUE, sw=1.2) +
            C(5.1, 6.1, 1.4, AMBER) +
            P("M2.2 12.6 6 8.2l3.1 3.6 1.7-1.7 3.1 2.8Z", fill=GREEN))


@icon("insert-link")
def _(g):
    if g == 24:
        return (P("M9.6 14.4 14.4 9.6", stroke=GRAY, w=2.2) +
                P("M10.6 6.6 13.2 4a4.8 4.8 0 0 1 6.8 6.8l-2.6 2.6",
                  stroke=BLUE, w=2.4) +
                P("M13.4 17.4 10.8 20A4.8 4.8 0 0 1 4 13.2l2.6-2.6",
                  stroke=BLUE, w=2.4))
    return (P("M6.4 9.6 9.6 6.4", stroke=GRAY, w=1.5) +
            P("M7 4.4 8.6 2.8a3.2 3.2 0 0 1 4.6 4.6l-1.6 1.6", stroke=BLUE, w=1.7) +
            P("M9 11.6l-1.6 1.6a3.2 3.2 0 0 1-4.6-4.6l1.6-1.6", stroke=BLUE, w=1.7))


@icon("insert-table")
def _(g):
    if g == 24:
        return (R(2.6, 4.4, 18.8, 15.2, PAPER, rx=2, stroke=BLUE, sw=1.4) +
                P("M2.6 6.4a2 2 0 0 1 2-2h14.8a2 2 0 0 1 2 2V9H2.6Z", fill=BLUE) +
                P("M2.6 14.3h18.8M9.4 9v10.6M15 9v10.6", stroke="#a9cbe8", w=1.2))
    return (R(1.5, 2.9, 13, 10.2, PAPER, rx=1.4, stroke=BLUE, sw=1.2) +
            P("M1.5 4.3a1.4 1.4 0 0 1 1.4-1.4h10.2a1.4 1.4 0 0 1 1.4 1.4V6h-13Z",
              fill=BLUE) +
            P("M1.5 9.6h13M6 6v7.1M10 6v7.1", stroke="#a9cbe8", w=1))


# Application and dialogs group --------------------------------------------

@icon("configure")
def _(g):
    if g == 24:
        return gear(12, 12, 10.4, 7.6, 8, BLUE) + C(12, 12, 3.4, PAPER)
    return gear(8, 8, 7, 5.1, 8, BLUE) + C(8, 8, 2.3, PAPER)


@icon("tools")
def _(g):
    if g == 24:
        return (C(15.8, 8.2, 4.4, "none", GRAY, 3.2,
                  extra='stroke-dasharray="20 8" transform="rotate(-52 15.8 8.2)"') +
                P("M13.2 11.2 5.4 19a2 2 0 0 0 2.8 2.8l7.8-7.8", stroke=GRAY, w=3.2))
    return (C(10.5, 5.4, 3, "none", GRAY, 2.2,
              extra='stroke-dasharray="13.6 5.5" transform="rotate(-52 10.5 5.4)"') +
            P("M8.8 7.2 3.6 12.4a1.3 1.3 0 0 0 1.9 1.9l5.2-5.2", stroke=GRAY, w=2.2))


@icon("system-search")
def _(g):
    if g == 24:
        return magnifier(10.4, 10.4, 6.8, 2.4)
    return magnifier(6.9, 6.9, 4.5, 1.7)


@icon("help-about")
def _(g):
    if g == 24:
        return (C(12, 12, 9.6, BLUE) + R(10.8, 10.2, 2.4, 7.2, PAPER, rx=1.2) +
                C(12, 7.2, 1.4, PAPER))
    return (C(8, 8, 6.4, BLUE) + R(7.2, 6.8, 1.6, 4.9, PAPER, rx=0.8) +
            C(8, 4.9, 1, PAPER))


@icon("help-contents")
def _(g):
    if g == 24:
        return (C(12, 12, 9.6, BLUE) +
                P("M8.8 9.4a3.3 3.3 0 1 1 4.5 3.1l-1.3.6v1.5", stroke=PAPER, w=2) +
                C(12, 17.4, 1.3, PAPER))
    return (C(8, 8, 6.4, BLUE) +
            P("M5.9 6.3a2.2 2.2 0 1 1 3 2l-.9.4v1", stroke=PAPER, w=1.4) +
            C(8, 11.6, 0.9, PAPER))


@icon("window-close")
def _(g):
    if g == 24:
        return P("M6 6 18 18M18 6 6 18", stroke=RED, w=2.8)
    return P("M4 4 12 12M12 4 4 12", stroke=RED, w=2)


@icon("window-new")
def _(g):
    return window(g) + badge(g, GREEN, g_plus)


@icon("application-exit")
def _(g):
    if g == 24:
        return (R(2.6, 2.6, 9.4, 18.8, BLUE_F, rx=1.6, stroke=BLUE, sw=1.4) +
                C(9.4, 12, 1.1, BLUE) +
                P("M13.6 12h7.8M18.2 8.4 21.8 12l-3.6 3.6", stroke=RED, w=2.2))
    return (R(1.5, 1.5, 6.2, 13, BLUE_F, rx=1.1, stroke=BLUE, sw=1.1) +
            C(6, 8, 0.8, BLUE) +
            P("M9.2 8h5.2M12 5.6 14.4 8 12 10.4", stroke=RED, w=1.6))


@icon("bookmark-new")
def _(g):
    if g == 24:
        return star(10.6, 10.4, 9, AMBER) + badge(24, GREEN, g_plus)
    return star(7, 7, 6, AMBER) + badge(16, GREEN, g_plus)


@icon("dialog-ok-apply")
def _(g):
    if g == 24:
        return C(12, 12, 9.6, GREEN) + P("M7.2 12.2 10.6 15.6 16.8 8.8",
                                         stroke=PAPER, w=2.4)
    return C(8, 8, 6.4, GREEN) + P("M4.9 8.2 7.1 10.4 11.1 5.9", stroke=PAPER, w=1.8)


@icon("dialog-cancel")
def _(g):
    if g == 24:
        return C(12, 12, 9.6, RED) + P("M8.4 8.4 15.6 15.6M15.6 8.4 8.4 15.6",
                                       stroke=PAPER, w=2.4)
    return C(8, 8, 6.4, RED) + P("M5.6 5.6 10.4 10.4M10.4 5.6 5.6 10.4",
                                 stroke=PAPER, w=1.8)


# --- theme assembly -----------------------------------------------------

PARENT = Path(os.environ.get("ELEVEN_TWILIGHT", ROOT / "src" / "ElevenTwilight"))


def version(name=NAME):
    """Theme version, read from the single source of truth: the VERSIONS file."""
    for line in VERSIONS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip()
    raise SystemExit(f"no version for {name} in {VERSIONS}")

INDEX = """[Icon Theme]
Name={name}
Comment=Colored Windows 11 style toolbar icons, on top of ElevenTwilight
Version={version}
Inherits=ElevenTwilight,breeze,Adwaita,hicolor
Example=document-save

FollowsColorScheme=true
KDE-Extensions=.svg
DisplayDepth=32

DesktopDefault=32
DesktopSizes=16,22,24,32,48,64
ToolbarDefault=16
ToolbarSizes=16,22,24,32,48
MainToolbarDefault=16
MainToolbarSizes=16,22,24,32,48
SmallDefault=16
SmallSizes=16,22,24,32,48
PanelDefault=24
PanelSizes=16,22,24,32,48,64
DialogDefault=24
DialogSizes=16,22,24,32,48,64

# Directory list
Directories={dirs}

[16/actions]
Context=Actions
Size=16
Type=Fixed

[22/actions]
Context=Actions
Size=22
Type=Fixed

[24/actions]
Context=Actions
Size=24
Type=Fixed

[32/actions]
Context=Actions
Size=32
Type=Fixed

[scalable/actions]
Context=Actions
Size=48
Type=Scalable
MinSize=33
MaxSize=512
"""

DIRS = ["16/actions", "22/actions", "24/actions", "32/actions",
        "scalable/actions"]
SIZE_DIRS = DIRS
# sizes with their own artwork; the others are symlinks to the 24 grid
DERIVED = ["22/actions", "32/actions", "scalable/actions"]

# Note: "-symbolic" names are deliberately not overridden. GTK apps recolor any
# symbolic icon on their own, flattening it to a single color, so a colored
# version looks worse there: symbolic icons stay the monochrome ones from the
# base theme. For the same reason the theme only ships the Actions context, so
# category and tray icons (apps, status) remain inherited.


def svg(grid, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{grid}" '
            f'height="{grid}" viewBox="0 0 {grid} {grid}">\n {body}\n</svg>\n')


def ink_box(body, grid, scale=10, threshold=32):
    """Box covered by the opaque pixels, in grid units.

    The body is rendered by librsvg straight at scale pixels per unit:
    rendering at the grid size and upscaling blurs the edges and inflates the
    box, and the ImageMagick internal renderer (MSVG) drops stroked paths
    entirely. The canvas has a margin of half a grid on every side, so ink
    drawn past the grid is measured instead of clipped. Pixels with alpha
    under threshold are antialiasing fringe and ignored."""
    pad = grid / 2
    span = grid + 2 * pad
    size = int(span * scale)
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(span)}" '
           f'height="{n(span)}" viewBox="{n(-pad)} {n(-pad)} {n(span)} {n(span)}">'
           f'{body}</svg>')
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, size, size
    Rsvg.Handle.new_from_data(doc.encode()).render_document(
        cairo.Context(surface), viewport)
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    alpha_at = 3 if sys.byteorder == "little" else 0
    x0, y0, x1, y1 = size, size, -1, -1
    for y in range(size):
        row = bytes(data[y * stride:y * stride + size * 4])[alpha_at::4]
        if max(row) < threshold:
            continue
        xs = [x for x, a in enumerate(row) if a >= threshold]
        x0, x1 = min(x0, xs[0]), max(x1, xs[-1])
        y0 = min(y0, y)
        y1 = y
    if x1 < 0:
        raise SystemExit("nothing rendered, cannot normalize")
    return (x0 / scale - pad, y0 / scale - pad,
            (x1 + 1 - x0) / scale, (y1 + 1 - y0) / scale)


def normalize(path, grid, body):
    """Rescale the icon until its ink fills the grid like the base theme icons
    do, and recenter it. Without librsvg the step is skipped."""
    x, y, w, h = ink_box(body, grid)
    s = min(TARGET[grid] / w, TARGET[grid] / h)
    s = max(0.85, min(1.35, s))
    tx = grid / 2 - s * (x + w / 2)
    ty = grid / 2 - s * (y + h / 2)
    if abs(s - 1) < 0.01 and abs(tx) < 0.05 and abs(ty) < 0.05:
        return False
    if (s * x + tx < -0.01 or s * y + ty < -0.01 or
            s * (x + w) + tx > grid + 0.01 or s * (y + h) + ty > grid + 0.01):
        raise SystemExit(f"{path}: normalized ink would leave the canvas")
    wrapped = G(body, f"translate({n(tx)} {n(ty)}) scale({n(s)})")
    path.write_text(svg(grid, wrapped))
    return True


def parent_dirs():
    """Directories of the parent theme, as listed in its index.theme."""
    index = configparser.ConfigParser(interpolation=None, strict=False)
    index.read(PARENT / "index.theme")
    return [PARENT / d for d in index["Icon Theme"]["Directories"].split(",")]


def parent_aliases():
    """Parent theme aliases pointing at the icons we are replacing.

    Once a name is in this theme it shadows the parent at every size and in
    every context, so an alias is taken only when all the copies of that name
    in the parent resolve to the same redrawn icon in an actions directory: a
    name that is a real icon somewhere, points to different icons at different
    sizes, or points to an app icon with the same file name (kfind is
    apps/system-search.svg) is left to the parent. Symbolic names are never
    taken, see the note above svg()."""
    canonical = {f"{k}.svg" for k in ICONS}
    targets = {}
    for d in parent_dirs():
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix != ".svg" or f.name in canonical:
                continue
            target = None
            if f.is_symlink():
                real = Path(os.path.realpath(f))
                target = (real.parent.name, real.name)
            targets.setdefault(f.name, set()).add(target)
    out = {}
    for alias, found in sorted(targets.items()):
        if alias.endswith("-symbolic.svg") or len(found) != 1:
            continue
        target = found.pop()
        if target and target[0] == "actions" and target[1] in canonical:
            out[alias] = target[1]
    return out


def main():
    ver = version()
    if THEME.exists():
        shutil.rmtree(THEME)
    for d in DIRS:
        (THEME / d).mkdir(parents=True)

    have_rsvg = Rsvg is not None
    scaled = 0
    for name, fn in sorted(ICONS.items()):
        for grid in (16, 24):
            f = THEME / f"{grid}/actions/{name}.svg"
            body = fn(grid)
            f.write_text(svg(grid, body))
            if have_rsvg and normalize(f, grid, body):
                scaled += 1
        for d in DERIVED:
            (THEME / d / f"{name}.svg").symlink_to(f"../../24/actions/{name}.svg")

    aliases = parent_aliases()
    for d in SIZE_DIRS:
        for alias, target in aliases.items():
            (THEME / d / alias).symlink_to(target)

    (THEME / "index.theme").write_text(
        INDEX.format(name=NAME, version=ver, dirs=",".join(DIRS)))

    print(f"{NAME} {ver}")
    print(f"{len(ICONS)} icons x 2 grids = {len(ICONS) * 2} SVG"
          f" ({scaled} normalized" + ("" if have_rsvg else ", librsvg missing")
          + ")")
    print(f"{len(ICONS) * len(DERIVED)} size links,"
          f" {len(aliases) * len(SIZE_DIRS)} aliases"
          f" ({len(aliases)} names per directory)")
    print(f"theme in {THEME}")



INSTALL_DEST = Path.home() / ".local/share/icons" / NAME


def install():
    """Install the theme as a symlink to the repo tree, so every rebuild is
    live without reinstalling."""
    if INSTALL_DEST.is_symlink() or INSTALL_DEST.is_file():
        INSTALL_DEST.unlink()
    elif INSTALL_DEST.exists():
        shutil.rmtree(INSTALL_DEST)
    INSTALL_DEST.parent.mkdir(parents=True, exist_ok=True)
    INSTALL_DEST.symlink_to(THEME, target_is_directory=True)
    print(f"installed: {INSTALL_DEST} -> {THEME}")


if __name__ == "__main__":
    main()
    if "--install" in sys.argv:
        install()
