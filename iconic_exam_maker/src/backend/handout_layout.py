"""
Handout Layout Engine  –  Iconic Academy
=========================================
Generates professional unit-handout PDFs with a metallic silver header.

Header layout
─────────────
  LEFT COLUMN (0 → 68 %)
    "Advanced Level"            italic, 16 pt
    "PHYSICS"                   bold,   27 pt  (letter-spaced)
    "MATTER AND"                bold,   user-controlled size (default 56 pt)
    "RADIATION"                 bold,   same size  ← optional second line
    "M.M. JEZEER AHAMED …"      italic, 14 pt

  RIGHT COLUMN (68 % → 100 %)
    "ICONIC"                    bold, letter-spaced, auto-fitted to column
    "ACADEMY"                   bold, letter-spaced, vertically centred

Config keys
───────────
    unit_name        str   Line 1 of unit name            (CHANGEABLE)
    unit_name_line2  str   Optional line 2 of unit name   (CHANGEABLE, can be "")
    unit_font_size   int   Font size in pt for unit name  (CHANGEABLE, default 56)
    subject          str   e.g. "PHYSICS"
    subject_level    str   e.g. "Advanced Level"
    institute_name   str   e.g. "ICONIC ACADEMY"
    lecturer_name    str
    lecturer_qual    str

Quick usage
───────────
    from src.backend.handout_layout import HandoutLayoutEngine

    engine = HandoutLayoutEngine()
    config = {
        "unit_name"       : "MATTER AND",        # line 1  ← change this
        "unit_name_line2" : "RADIATION",          # line 2  ← change this (or "")
        "unit_font_size"  : 56,                   # pt size ← change this
        "subject"         : "PHYSICS",
        "subject_level"   : "Advanced Level",
        "institute_name"  : "ICONIC ACADEMY",
        "lecturer_name"   : "M.M. JEZEER AHAMED",
        "lecturer_qual"   : "B.Sc (Engineering)",
    }
    pdf_path = engine.generate_handout(questions, "output.pdf", config)
"""

import os
import math
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont


class HandoutLayoutEngine:
    """
    Generates professional unit handouts with a metallic silver header.
    All measurements in mm / pt; converted to 300-DPI pixels internally.
    """

    PAGE_W  = 2480   # A4 @ 300 DPI
    PAGE_H  = 3508
    MARGIN  = 118    # ≈ 10 mm

    _Q_NUM_X  = 20   # question number x-offset from left margin
    _Q_IMG_X  = 135  # question image  x-offset from left margin

    # ── default header sizes (pt) ─────────────────────────────────────────
    _PT_LEVEL   = 16   # "Advanced Level"
    _PT_SUBJECT = 27   # "PHYSICS"
    _PT_UNIT    = 56   # unit name default (user can override via config)
    _PT_LECT    = 14   # lecturer line

    _LEFT_FRAC  = 0.68  # fraction of usable width for the left column

    def __init__(self, output_dir: str = "exam_papers"):
        self.output_dir = output_dir
        self._font_dir  = os.path.join("assets", "fonts")

    # ══════════════════════════════════════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════════════════════════════════════

    def generate_handout(self,
                         questions : list,
                         output_path: str  = None,
                         config    : dict  = None) -> str | None:
        """
        Generate a unit-handout PDF.

        Parameters
        ----------
        questions    list[str | dict]  paths to question images (or dicts with 'img_path')
        output_path  str               destination PDF (auto-named if None)
        config       dict              see module docstring

        Returns
        -------
        str path of the saved PDF, or None on failure.
        """
        if config is None:
            config = {}

        PW, PH = self.PAGE_W, self.PAGE_H
        M      = self.MARGIN
        pages  = []
        pg_num = 1

        curr_page, draw = self._new_page(PW, PH, config)
        hdr_bottom      = self._draw_header(curr_page, draw, config)

        y = hdr_bottom + self._mm(4)
        draw.line([(M, y), (PW - M, y)], fill=(70, 70, 70), width=3)
        y += self._mm(4)

        Q_NUM_X = M + self._Q_NUM_X
        Q_IMG_X = M + self._Q_IMG_X
        Q_MAX_W = PW - Q_IMG_X - M
        f_qnum  = self._font("timesbd.ttf", 14)

        q_paths = []
        for item in (questions or []):
            q_paths.append(item.get("img_path", "") if isinstance(item, dict) else str(item))

        for i, qp in enumerate(q_paths):
            if not qp or not os.path.exists(qp):
                continue
            img    = Image.open(qp)
            ow, oh = img.size
            scale  = min(1.0, Q_MAX_W / ow)
            tw, th = int(ow * scale), int(oh * scale)
            if scale < 1.0:
                img = img.resize((tw, th), Image.Resampling.LANCZOS)

            if y + th + self._mm(5) > PH - M - self._mm(12):
                self._draw_footer(draw, PW, PH, pg_num, config)
                pages.append(curr_page)
                pg_num += 1
                curr_page, draw = self._new_page(PW, PH, config)
                y = M + self._mm(6)

            draw.text((Q_NUM_X, y + 6), f"{i + 1}.", font=f_qnum, fill="black")
            curr_page.paste(img, (Q_IMG_X, y))
            y += th + self._mm(5)

        self._draw_footer(draw, PW, PH, pg_num, config)
        pages.append(curr_page)

        os.makedirs(self.output_dir, exist_ok=True)
        if not output_path:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = config.get("unit_name", "Handout").replace(" ", "_")[:30]
            output_path = os.path.join(self.output_dir, f"Handout_{slug}_{ts}.pdf")
        try:
            pages[0].save(output_path, "PDF", resolution=300.0,
                          save_all=True, append_images=pages[1:])
            return output_path
        except Exception as exc:
            print(f"[HandoutLayoutEngine] save error: {exc}")
            return None

    # ══════════════════════════════════════════════════════════════════════
    #  Header
    # ══════════════════════════════════════════════════════════════════════

    def _draw_header(self,
                     page  : Image.Image,
                     draw  : ImageDraw.ImageDraw,
                     config: dict) -> int:
        """Draw the metallic banner. Returns absolute y of the bottom edge."""

        # ── unpack config ─────────────────────────────────────────────────
        unit_line1  = str(config.get("unit_name",       "UNIT NAME")).upper().strip()
        unit_line2  = str(config.get("unit_name_line2", "")).upper().strip()
        unit_pt     = int(config.get("unit_font_size",  self._PT_UNIT))
        subject     = str(config.get("subject",          "PHYSICS")).upper()
        level_txt   = str(config.get("subject_level",    "Advanced Level"))
        inst_name   = str(config.get("institute_name",   "ICONIC ACADEMY")).upper()
        lect_name   = str(config.get("lecturer_name",    "M.M. JEZEER AHAMED"))
        lect_qual   = str(config.get("lecturer_qual",    "B.Sc (Engineering)"))
        white_bg    = bool(config.get("white_background", False))

        M   = self.MARGIN
        hx  = M
        hy  = M
        hw  = self.PAGE_W - 2 * M

        left_w  = int(hw * self._LEFT_FRAC)
        right_w = hw - left_w

        # ── fonts ─────────────────────────────────────────────────────────
        f_level   = self._font("timesi.ttf",  self._PT_LEVEL)
        f_subject = self._font("timesbd.ttf", self._PT_SUBJECT)
        f_lect    = self._font("timesbi.ttf", self._PT_LECT)

        # Unit name: use user's chosen pt, auto-shrink if either line overflows
        avail_unit_w = left_w - self._mm(8)
        unit_lines   = [unit_line1] + ([unit_line2] if unit_line2 else [])
        longest_line = max(unit_lines, key=lambda t: len(t))
        f_unit = self._fit_font_to_width("arialbd.ttf", unit_pt, longest_line, avail_unit_w)

        # Institute: auto-fit the longer word to the right column
        inst_words = inst_name.split()
        inst_w1    = inst_words[0]                  if inst_words     else inst_name
        inst_w2    = " ".join(inst_words[1:])        if len(inst_words) > 1 else ""
        avail_inst = right_w - self._mm(6)
        # Fit font to the longer of the two institute words
        inst_ref   = inst_w2 if len(inst_w2) >= len(inst_w1) else inst_w1
        f_inst     = self._fit_font_to_width("timesbd.ttf", 36, inst_ref, avail_inst)

        # ── measure heights ───────────────────────────────────────────────
        PAD_TOP    = self._mm(5)
        PAD_BOTTOM = self._mm(6)   # slightly taller — lecturer needs breathing room
        LINE_GAP   = self._mm(2)

        lh_level    = self._text_h(f_level,   level_txt)
        lh_subject  = self._text_h(f_subject, subject)
        lh_lect     = self._text_h(f_lect,    lect_name)
        lh_unit_one = self._text_h(f_unit,    unit_line1)
        lh_unit_blk = lh_unit_one * len(unit_lines) + (len(unit_lines) - 1) * LINE_GAP

        hh = (PAD_TOP
              + lh_level   + LINE_GAP
              + lh_subject + LINE_GAP
              + lh_unit_blk + LINE_GAP
              + lh_lect
              + PAD_BOTTOM)
        hh = max(hh, self._mm(38))

        # ── background ────────────────────────────────────────────────────
        if white_bg:
            draw.rectangle([(hx, hy), (hx + hw, hy + hh)], fill=(255, 255, 255))
        else:
            page.paste(self._metallic_bg(hw, hh), (hx, hy))

        # ── colours chosen by background mode ─────────────────────────────
        if white_bg:
            text_main   = (0,   0,   0)    # pure black text
            text_shadow = (150, 150, 150)  # subtle grey shadow
            div_col     = (180, 180, 180)  # light grey divider
            border_col  = (0,   0,   0)
            border_w    = self._pt(1.5)
        else:
            text_main   = (22,  22,  22)
            text_shadow = (10,  10,  10)
            div_col     = (80,  80,  80)
            border_col  = (40,  40,  40)
            border_w    = self._pt(3)

        # ── thin vertical divider between columns ─────────────────────────
        div_x = hx + left_w
        draw.line(
            [(div_x, hy + self._mm(4)), (div_x, hy + hh - self._mm(4))],
            fill=div_col, width=2,
        )

        # ══ LEFT COLUMN ═══════════════════════════════════════════════════
        tx = hx + self._mm(5)
        ty = hy + PAD_TOP

        self._draw_text(draw, (tx, ty), level_txt, f_level,
                        main=text_main, shadow=text_shadow,
                        depth=2, white_bg=white_bg)
        ty += lh_level + LINE_GAP

        self._draw_spaced(draw, (tx, ty), subject, f_subject, spacing_px=4,
                          color=text_main,
                          shadow=(not white_bg))
        ty += lh_subject + LINE_GAP

        # ══  UNIT NAME  (1 or 2 lines, user-controlled)  ══
        for line in unit_lines:
            self._draw_text(draw, (tx, ty), line, f_unit,
                            main=text_main, shadow=text_shadow,
                            depth=5, white_bg=white_bg)
            ty += lh_unit_one + LINE_GAP

        # Lecturer – hard clamp: never overlap unit name, never fall outside border
        lect_full  = f"{lect_name}  {lect_qual}"
        lect_max_y = hy + hh - PAD_BOTTOM - lh_lect
        ty_lect    = max(ty, min(ty, lect_max_y))
        self._draw_text(draw, (tx, ty_lect), lect_full, f_lect,
                        main=text_main, shadow=text_shadow,
                        depth=2, white_bg=white_bg)

        # ══ RIGHT COLUMN – institute name, vertically centred ═════════════
        rz_x  = hx + left_w
        rz_cx = rz_x + right_w // 2

        lh_inst1 = self._text_h(f_inst, inst_w1)
        lh_inst2 = self._text_h(f_inst, inst_w2) if inst_w2 else 0
        inst_gap  = self._mm(2)
        inst_blk  = lh_inst1 + (inst_gap + lh_inst2 if inst_w2 else 0)
        iy = hy + (hh - inst_blk) // 2

        def spaced_cx(text):
            w = self._spaced_width(draw, text, f_inst, spacing_px=6)
            return rz_cx - w // 2

        self._draw_spaced(draw, (spaced_cx(inst_w1), iy),
                          inst_w1, f_inst, spacing_px=6,
                          color=text_main, shadow=(not white_bg))
        if inst_w2:
            iy += lh_inst1 + inst_gap
            self._draw_spaced(draw, (spaced_cx(inst_w2), iy),
                              inst_w2, f_inst, spacing_px=6,
                              color=text_main, shadow=(not white_bg))

        # ── border ────────────────────────────────────────────────────────
        draw.rounded_rectangle(
            [(hx, hy), (hx + hw, hy + hh)],
            radius=self._pt(12),
            outline=border_col,
            width=border_w,
        )

        return hy + hh

    # ══════════════════════════════════════════════════════════════════════
    #  Footer
    # ══════════════════════════════════════════════════════════════════════

    def _draw_footer(self, draw, pw, ph, pg_num, config):
        M  = self.MARGIN
        fy = ph - M - self._mm(8)
        f  = self._font("times.ttf", 11)
        draw.line([(M, fy), (pw - M, fy)], fill="black", width=2)

        left = (f"{config.get('lecturer_name', '')}  "
                f"{config.get('lecturer_qual', '')}").strip()
        if left:
            draw.text((M + self._mm(2), fy + self._mm(2)), left, font=f, fill="black")

        pg  = f"- {pg_num} -"
        pw_ = draw.textlength(pg, font=f)
        draw.text((pw // 2 - int(pw_) // 2, fy + self._mm(2)), pg, font=f, fill="black")

    # ══════════════════════════════════════════════════════════════════════
    #  Drawing helpers
    # ══════════════════════════════════════════════════════════════════════

    def _draw_text(self, draw, pos, text, font,
                   main=(22, 22, 22), shadow=(10, 10, 10),
                   depth=3, white_bg=False):
        """
        Draw text with appropriate effect for the chosen background.

        Metallic (white_bg=False): 3-layer emboss — shadow → highlight → main.
        White    (white_bg=True):  2-layer flat — subtle grey shadow → black main.
        """
        x, y = int(pos[0]), int(pos[1])
        if white_bg:
            # Flat black text with a very soft grey drop-shadow
            draw.text((x + depth, y + depth), text, font=font, fill=shadow)
            draw.text((x, y),                 text, font=font, fill=main)
        else:
            # Full 3-layer emboss for the metallic look
            highlight_c = (248, 248, 248)
            draw.text((x + depth, y + depth), text, font=font, fill=shadow)
            draw.text((x - 1,     y - 1),     text, font=font, fill=highlight_c)
            draw.text((x,         y),         text, font=font, fill=main)

    def _draw_spaced(self, draw, pos, text, font,
                     spacing_px=4, color=(35, 35, 35), shadow=False):
        """Render text with manual letter spacing."""
        cx, cy = int(pos[0]), int(pos[1])
        for ch in text:
            if shadow:
                draw.text((cx + 2, cy + 2), ch, font=font, fill=(10, 10, 10))
            draw.text((cx, cy), ch, font=font, fill=color)
            cx += int(draw.textlength(ch, font=font)) + spacing_px

    def _spaced_width(self, draw, text, font, spacing_px=4) -> int:
        total = sum(int(draw.textlength(ch, font=font)) + spacing_px for ch in text)
        return max(total - spacing_px, 0)

    # ══════════════════════════════════════════════════════════════════════
    #  Metallic background
    # ══════════════════════════════════════════════════════════════════════

    def _metallic_bg(self, width: int, height: int) -> Image.Image:
        """Brushed-silver vertical gradient with shimmer bands."""
        img  = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        stops = [
            (0.00,  62), (0.05, 130), (0.18, 168), (0.35, 190),
            (0.50, 180), (0.65, 163), (0.82, 146), (0.94, 130), (1.00, 65),
        ]

        def interp(t):
            for i in range(len(stops) - 1):
                t0, v0 = stops[i];  t1, v1 = stops[i + 1]
                if t0 <= t <= t1:
                    r = (t - t0) / (t1 - t0)
                    return int(v0 + (v1 - v0) * r)
            return int(stops[-1][1])

        for row in range(height):
            t = row / max(height - 1, 1)
            v = max(50, min(225, interp(t) + int(8 * math.sin(t * math.pi * 12))))
            draw.line([(0, row), (width, row)], fill=(v, v, v))

        return img

    # ══════════════════════════════════════════════════════════════════════
    #  Page helpers
    # ══════════════════════════════════════════════════════════════════════

    def _new_page(self, pw, ph, config):
        page = Image.new("RGB", (pw, ph), "white")
        draw = ImageDraw.Draw(page)
        if config.get("show_border", True):
            self._draw_border(draw, pw, ph)
        return page, draw

    def _draw_border(self, draw, pw, ph):
        M = self.MARGIN
        draw.rectangle([(M - 20, M - 20), (pw - M + 20, ph - M + 20)],
                        outline="black", width=7)
        draw.rectangle([(M - 5,  M - 5),  (pw - M + 5,  ph - M + 5)],
                        outline="black", width=2)

    # ══════════════════════════════════════════════════════════════════════
    #  Unit conversion & font helpers
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _mm(mm: float) -> int:
        return int(mm * 300 / 25.4)

    @staticmethod
    def _pt(pt: float) -> int:
        return int(pt * 300 / 72)

    def _font(self, name: str, size_pt: float) -> ImageFont.FreeTypeFont:
        px   = self._pt(size_pt)
        path = os.path.join(self._font_dir, name)
        try:
            return ImageFont.truetype(path if os.path.exists(path) else name, px)
        except Exception:
            return ImageFont.load_default()

    def _fit_font_to_width(self, name: str, max_pt: float,
                           text: str, max_px: int) -> ImageFont.FreeTypeFont:
        """Largest font ≤ max_pt that renders text within max_px. Shrinks by 1 pt."""
        size = float(max_pt)
        while size >= 8:
            f = self._font(name, size)
            try:
                w = int(f.getlength(text))
            except Exception:
                w = int(sum(f.getbbox(ch)[2] for ch in text))
            if w <= max_px:
                return f
            size -= 1
        return self._font(name, 8)

    @staticmethod
    def _text_h(font, text: str) -> int:
        """
        Return the line-advance height for *font*.

        Uses 82 % of the font's em-square pixel size rather than the tight
        getbbox bounding box.  getbbox only captures actual glyph extents,
        which for all-caps Latin text can be 25 % smaller than the em square —
        causing lines to look cramped and the shadow to bleed into the next row.
        82 % gives reliable, consistent spacing with a natural gap between lines.
        """
        try:
            return int(font.size * 0.82)
        except Exception:
            try:
                bb = font.getbbox(text)
                return bb[3] - bb[1]
            except Exception:
                return 40
