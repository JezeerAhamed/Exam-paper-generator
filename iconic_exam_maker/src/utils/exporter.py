import fitz
import os
import json
import traceback
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QFontMetrics, QFontDatabase
from PySide6.QtCore import Qt, QRect

class PDFExporter:
    @staticmethod
    def _draw_text_qt(pos, text, font_name, size_pt, bold=False, italic=False, color='black'):
        """Renders text using Qt's engine for perfect shaping/ligatures, then converts to PIL"""
        # 1. Load Font (Handle both family names and file paths/assets)
        font_family = font_name
        
        # Check if font_name maps to a file in assets/fonts (e.g. "Latha" -> "latha.ttf")
        # We'll try to find the actual .ttf name first
        font_map = {
            "Latha": "latha.ttf",
            "Nirmala UI": "Nirmala.ttf",
            "Vijaya": "vijaya.ttf",
            "Iskoola Pota": "iskpota.ttf"
        }
        
        font_file = font_map.get(font_name, font_name)
        if not font_file.endswith(".ttf"): font_file += ".ttf"
        
        font_path = os.path.join("assets", "fonts", font_file)
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        
        font = QFont(font_family, size_pt)
        if bold: font.setBold(True)
        if italic: font.setItalic(True)
        
        # 2. Measure Text
        metrics = QFontMetrics(font)
        w = metrics.horizontalAdvance(text) + 20
        h = metrics.height() + 10
        
        # 3. Render to QImage
        qimg = QImage(w, h, QImage.Format.Format_ARGB32)
        qimg.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        painter.setPen(QColor(color))
        # Draw at x=5, y=ascent (baseline)
        painter.drawText(5, metrics.ascent(), text)
        painter.end()
        
        # 4. Convert to PIL Image
        ptr = qimg.bits()
        from PIL import Image
        pil_img = Image.frombuffer('RGBA', (w, h), ptr, 'raw', 'BGRA', 0, 1).copy()
        
        # 5. Return image and the offset-adjusted position
        # We adjust pos to simulate Pillow's top-left drawing behavior
        paste_pos = (int(pos[0] - 5), int(pos[1]))
        return pil_img, paste_pos

    @staticmethod
    def _load_subject_map():
        """Loads subject mappings from JSON or returns default"""
        default_map = {
            "CHEMISTRY": ("රසායන විද්‍යාව", "இரசாயனவியல்"), 
            "PHYSICS": ("භෞතික විද්‍යාව", "பௌதிகவியல்"), 
            "BIOLOGY": ("ජීව විද්‍යාව", "உயிரியல்")
        }
        try:
            config_path = os.path.join("config", "subjects.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert JSON {Subject: {sinhala: x, tamil: y}} to format
                    loaded_map = {}
                    for subj, trans in data.items():
                        loaded_map[subj.upper()] = (trans.get("sinhala", ""), trans.get("tamil", ""))
                    return loaded_map
        except Exception as e:
            print(f"Error loading subjects.json: {e}")
        return default_map

    @staticmethod
    def generate_exam_pdf(questions, output_path, title="Exam Paper", config=None):
        """
        Generates professional exam paper PDF with EXACT specifications matching reference.
        Uses specialized fonts for Tamil (Latha) and Sinhala (Iskoola Pota) for best rendering.
        """
        if config is None:
            config = {}
        
        # Extract config
        subject = config.get("subject", "PHYSICS").upper()
        
        # Load Dynamic Subject Map
        subject_map = PDFExporter._load_subject_map()
        subj_sinhala, subj_tamil = subject_map.get(subject, (subject.title(), subject.title()))

        exam_series = config.get("exam_series", "Final Exam Series")
        paper_number = config.get("paper_number", "1")
        duration = config.get("duration", "01 hour")
        footer_quote = str(config.get("footer_quote", "Find simplicity in the universe.")).strip()
        if not footer_quote:
            footer_quote = "Find simplicity in the universe."
        
        # Default Codes: 01 | T | I
        paper_code_1 = config.get("paper_code_1", "01")
        paper_code_2 = config.get("paper_code_2", "T")
        part_code = str(config.get("part_code", config.get("paper_code_3", "I")) or "I")
        paper_code_3 = part_code
        
        # Updated Lecturer Info
        lecturer_name = config.get("lecturer_name", "M.M.JEZEER AHAMED")
        lecturer_qualification = config.get("lecturer_qualification", "B.sc (Engineering)")
        
        # Logo Logic - Robust Search
        logo_path = config.get("logo_path", "logo.png")
        if not os.path.exists(logo_path):
            # Try fallbacks
            for candidate in ["assets/logo.png", "assets/images/logo.png", "logo.jpg"]:
                if os.path.exists(candidate):
                    logo_path = candidate
                    break
        
        # A4 @ 300 DPI
        PW, PH = 2480, 3508
        DPI = 300
        
        # Helper conversions
        def mm_to_px(mm): return int(mm * DPI / 25.4)
        def pt_to_px(pt): return int(pt * DPI / 72)
        
        # Layout overrides (defaults match current design)
        layout = config.get("layout", {})
        def lmm(key, default): return float(layout.get(key, default))
        def lpt(key, default): return float(layout.get(key, default))

        # Measurements
        BORDER_MARGIN = mm_to_px(lmm("border_margin_mm", 10))
        BORDER_RADIUS = pt_to_px(lpt("border_radius_pt", 15))
        BORDER_WIDTH = pt_to_px(lpt("border_width_pt", 2))
        
        # --- FONT LOADING LOGIC ---
        ASSETS_FONT_DIR = os.path.join("assets", "fonts")
        
        def get_font_path(name):
            # Check bundled first
            bundled = os.path.join(ASSETS_FONT_DIR, name)
            if os.path.exists(bundled):
                return bundled
            return name # System fallback

        def get_font(name_pref, size_pt, bold=False):
            size_px = pt_to_px(size_pt)
            font_names = []
            if name_pref: font_names.append(name_pref)
            
            # Append Bundled Names
            if bold:
                font_names.extend(["arialbd.ttf", "NirmalaB.ttf"])
            else:
                font_names.extend(["arial.ttf", "Nirmala.ttf"])
                
            for name in font_names:
                try:
                    # Try bundled path first
                    path = get_font_path(name)
                    return ImageFont.truetype(path, size_px)
                except:
                    continue
            return ImageFont.load_default()

        # User's Font Preference
        pref_font_name = config.get("tamil_font", "Latha")
        
        # Dedicated font loaders
        def get_sinhala_font(size_pt, bold=False):
            size_px = pt_to_px(size_pt)
            # Priority: Iskoola Pota (Standard Sinhala), Nirmala UI
            names = ["iskpota.ttf", "Nirmala.ttf"] 
            if bold: names = ["iskpotab.ttf", "NirmalaB.ttf"]
            
            for name in names:
                try: 
                    path = get_font_path(name)
                    return ImageFont.truetype(path, size_px)
                except: continue
            return get_font(None, size_pt, bold)

        def get_tamil_font(size_pt, bold=False):
            size_px = pt_to_px(size_pt)
            
            # Map friendly names to filenames
            font_map = {
                "Latha": "latha.ttf" if not bold else "lathab.ttf",
                "Nirmala UI": "Nirmala.ttf" if not bold else "NirmalaB.ttf",
                "Vijaya": "vijaya.ttf" if not bold else "vijayab.ttf"
            }
            
            pref_file = font_map.get(pref_font_name, "latha.ttf")
            
            # Priority: User selection, then fallbacks
            names = [pref_file, "latha.ttf", "vijaya.ttf", "Nirmala.ttf"]
            if bold: names = [pref_file, "lathab.ttf", "vijayab.ttf", "NirmalaB.ttf"]
            
            for name in names:
                try: 
                    path = get_font_path(name)
                    return ImageFont.truetype(path, size_px)
                except: continue
            return get_font(None, size_pt, bold)

        # Load Fonts
        sizes = config.get("font_sizes", {})
        
        def get_s(key, default):
            return sizes.get(key, default)

        f_subject_header = get_font("arialbd.ttf", 26, True) 
        
        # Script-specific headers
        f_header_sinhala = get_sinhala_font(10, True)
        f_header_tamil = get_tamil_font(10, True)
        
        f_series = get_font("timesbi.ttf", get_s("series", 18), True)
        f_adv_level = get_font("timesi.ttf", get_s("adv_level", 18), False)
        f_subject_header = get_font("timesbd.ttf", get_s("subject_header", 40), True)
        f_paper_num = get_font("timesbd.ttf", get_s("paper_num", 36), True)
        
        # Box Labels - Calibrated to 13pt for max fill in 11mm height
        f_box_sinhala = get_sinhala_font(get_s("box_labels", 13), False)
        f_box_tamil = get_tamil_font(get_s("box_labels", 13), False)
        f_box_english = get_font("Nirmala.ttf", get_s("box_labels", 13), False)
        f_box_label_bold = get_font("timesbd.ttf", get_s("box_labels", 13), True)
        
        f_code = get_font("timesbd.ttf", get_s("paper_code", 16), True)
        f_time = get_font("timesbi.ttf", get_s("time", 14), True)
        
        # Tamil Instructions
        f_tamil_instr = get_tamil_font(get_s("instructions", 20), False)
        
        # Constants
        f_const_desc = get_tamil_font(get_s("constants", 8), False) # Using Tamil font for description
        f_const_val = get_font("arial.ttf", get_s("constants", 8), False) # Arial handles unicode superscripts well
        
        f_marks = get_font("timesbi.ttf", 13, True)
        f_lecturer = get_font("timesbd.ttf", get_s("lecturer", 14), True)
        f_lecturer_qual = get_font("times.ttf", get_s("lecturer_qual", 12), False)
        
        f_question_num = get_font("timesbd.ttf", 12, True)
        footer_size_src = sizes.get("footer", layout.get("footer_font_size", 11))
        try:
            footer_font_size = int(footer_size_src)
        except Exception:
            footer_font_size = 11
        f_footer = get_font("times.ttf", footer_font_size, False)
        
        pages = []
        page_num = 1

        def qt_font_metrics(font_name, size_pt, bold=False, italic=False):
            font_family = font_name
            font_map = {
                "Latha": "latha.ttf",
                "Nirmala UI": "Nirmala.ttf",
                "Vijaya": "vijaya.ttf",
                "Iskoola Pota": "iskpota.ttf"
            }
            font_file = font_map.get(font_name, font_name)
            if not font_file.endswith(".ttf"):
                font_file += ".ttf"
            font_path = os.path.join("assets", "fonts", font_file)
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            font = QFont(font_family, size_pt)
            if bold:
                font.setBold(True)
            if italic:
                font.setItalic(True)
            metrics = QFontMetrics(font)
            return metrics.height()

        def qt_text_width(font_name, size_pt, text, bold=False, italic=False):
            font_family = font_name
            font_map = {
                "Latha": "latha.ttf",
                "Nirmala UI": "Nirmala.ttf",
                "Vijaya": "vijaya.ttf",
                "Iskoola Pota": "iskpota.ttf"
            }
            font_file = font_map.get(font_name, font_name)
            if not font_file.endswith(".ttf"):
                font_file += ".ttf"
            font_path = os.path.join("assets", "fonts", font_file)
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            font = QFont(font_family, size_pt)
            if bold:
                font.setBold(True)
            if italic:
                font.setItalic(True)
            metrics = QFontMetrics(font)
            return metrics.horizontalAdvance(text)

        def fit_qt_size(font_name, size_pt, max_h, bold=False, italic=False):
            size = size_pt
            while size > 6 and qt_font_metrics(font_name, size, bold, italic) > max_h:
                size -= 1
            return size

        def fit_pil_size(font_file, size_pt, max_h, bold=False):
            size = size_pt
            while size > 6:
                test_font = get_font(font_file, size, bold)
                bbox = test_font.getbbox("Ag")
                if (bbox[3] - bbox[1]) <= max_h:
                    return size
                size -= 1
            return size
        
        try:
            curr_page = Image.new('RGB', (PW, PH), 'white')
            draw = ImageDraw.Draw(curr_page)
            
            # --- MAIN BORDER ---
            PDFExporter._draw_rounded_rectangle(
                draw, [(BORDER_MARGIN, BORDER_MARGIN), (PW - BORDER_MARGIN, PH - BORDER_MARGIN)],
                radius=BORDER_RADIUS, outline='black', width=BORDER_WIDTH
            )
            
            y = BORDER_MARGIN + mm_to_px(4)
            row1_h = mm_to_px(lmm("row1_h_mm", 22))
            
            # 1. Subject Box (Left) - "ADVANCED LEVEL" (Stylish)
            left_x = BORDER_MARGIN + mm_to_px(5)
            
            # Header Label (Italic Title Case)
            draw.text((left_x, y + mm_to_px(1)), "Advanced Level", font=f_adv_level, fill='black')

            def draw_spaced_text(text, x, y, font, spacing_px):
                cx = x
                for ch in text:
                    draw.text((cx, y), ch, font=font, fill='black')
                    cx += draw.textlength(ch, font=font) + spacing_px

            # Subject Name (Large with letter spacing)
            draw_spaced_text(subject.upper(), left_x, y + mm_to_px(7), f_subject_header, pt_to_px(1.5))
            
            # 2. Logo (Center)
            logo_w, logo_h = mm_to_px(lmm("logo_w_mm", 50)), mm_to_px(lmm("logo_h_mm", 18))
            logo_x = (PW - logo_w) // 2
            PDFExporter._draw_rounded_rectangle(
                draw, [(logo_x, y), (logo_x + logo_w, y + logo_h)],
                radius=pt_to_px(lpt("logo_radius_pt", 8)), fill='#D3D3D3',
                outline='black', width=pt_to_px(lpt("logo_border_pt", 1))
            )
            inner_pad = pt_to_px(lpt("logo_inner_pad_pt", 2))
            PDFExporter._draw_rounded_rectangle(
                draw, [(logo_x + inner_pad, y + inner_pad), (logo_x + logo_w - inner_pad, y + logo_h - inner_pad)],
                radius=pt_to_px(lpt("logo_inner_radius_pt", 6)),
                outline='black', width=pt_to_px(lpt("logo_inner_border_pt", 0.8))
            )
            if logo_path and os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    logo.thumbnail(
                        (logo_w - mm_to_px(lmm("logo_pad_w_mm", 3)), logo_h - mm_to_px(lmm("logo_pad_h_mm", 2))),
                        Image.Resampling.LANCZOS
                    )
                    lx = logo_x + (logo_w - logo.width) // 2
                    ly = y + (logo_h - logo.height) // 2
                    curr_page.paste(logo, (lx, ly), logo if logo.mode=='RGBA' else None)
                except: pass
            
            # 3. Series & Number (Right)
            right_margin = PW - BORDER_MARGIN - mm_to_px(5)
            series_w = draw.textlength(exam_series, font=f_series)
            num_box_size = mm_to_px(lmm("num_box_size_mm", 14))
            num_box_x = right_margin - num_box_size
            
            PDFExporter._draw_rounded_rectangle(
                draw, [(num_box_x, y + mm_to_px(1)), (num_box_x + num_box_size, y + mm_to_px(1) + num_box_size)],
                radius=pt_to_px(lpt("num_box_radius_pt", 7)),
                outline='black', width=pt_to_px(lpt("num_box_border_pt", 1))
            )
            num_w = draw.textlength(paper_number, font=f_paper_num)
            draw.text((num_box_x + (num_box_size - num_w)/2, y + mm_to_px(1) - pt_to_px(2)), 
                     paper_number, font=f_paper_num, fill='black')
            draw.text((num_box_x - series_w - mm_to_px(3), y + mm_to_px(5)), 
                     exam_series, font=f_series, fill='black')

            # --- SEPARATOR 1 ---
            y += row1_h + mm_to_px(2)
            draw.line([(BORDER_MARGIN, y), (PW - BORDER_MARGIN, y)], fill='black', width=pt_to_px(1))
            
            # --- ROW 2: Language Box | Codes | Time ---
            y += mm_to_px(2)
            row2_h = mm_to_px(lmm("row2_h_mm", 12))
            
            # 1. Language Box (Tamil / English + Paper Code)
            lang_box_w = mm_to_px(lmm("lang_box_w_mm", 34))
            lang_box_x = BORDER_MARGIN + mm_to_px(5)
            PDFExporter._draw_rounded_rectangle(
                draw, [(lang_box_x, y), (lang_box_x + lang_box_w, y + row2_h)],
                radius=pt_to_px(lpt("lang_box_radius_pt", 6)),
                outline='black', width=pt_to_px(lpt("lang_box_border_pt", 1))
            )
            
            # Text inside lang box (fit to 3 equal bands)
            lx = lang_box_x + mm_to_px(3)
            rx = lang_box_x + lang_box_w - mm_to_px(6)
            paper_num_val = part_code

            pad_y = mm_to_px(0.0)
            band_h = int(row2_h - pad_y * 2)

            base_size = get_s("box_labels", 24)
            t_fit = fit_qt_size(pref_font_name, base_size, band_h, True)
            i_fit = fit_pil_size("timesbd.ttf", base_size, band_h, True)

            # Force a minimum size so the text doesn't look too small
            min_size = get_s("box_labels_min", 22)
            t_fit = max(t_fit, min_size)
            i_fit = max(i_fit, min_size)

            # Use a single uniform size for Tamil and the "I"
            uniform_size = min(t_fit, i_fit)
            t_size = uniform_size
            i_size = uniform_size

            f_box_label_fit = get_font("timesbd.ttf", i_size, True)

            # Tamil line only (centered vertically)
            t_h = qt_font_metrics(pref_font_name, t_size, True, False)
            t_y = y + (row2_h - t_h) // 2
            t_img, t_pos = PDFExporter._draw_text_qt((lx, t_y), subj_tamil, pref_font_name, t_size, True)
            curr_page.paste(t_img, t_pos, t_img)

            # Single "I" centered within a right-side area
            i_bbox = f_box_label_fit.getbbox("I")
            i_w = i_bbox[2] - i_bbox[0]
            i_h = i_bbox[3] - i_bbox[1]
            i_area_w = mm_to_px(8)
            i_area_x = lang_box_x + lang_box_w - i_area_w - mm_to_px(2)
            ix = i_area_x + (i_area_w - i_w) // 2 - i_bbox[0]
            iy = y + (row2_h - i_h) // 2 - i_bbox[1]
            draw.text((ix, iy), paper_num_val, font=f_box_label_fit, fill='black')
            
            # 2. Codes 01 | T | I
            code_base_x = (PW // 2) - mm_to_px(lmm("code_base_offset_mm", 14))
            code_w = mm_to_px(lmm("code_w_mm", 10))
            code_y = y + (row2_h - code_w) // 2
            
            def draw_code_box(x, text):
                # Outer Black Box
                PDFExporter._draw_rounded_rectangle(
                    draw, [(x, code_y), (x + code_w, code_y + code_w)],
                    radius=pt_to_px(lpt("code_radius_pt", 6)), fill='black', outline='black',
                    width=pt_to_px(lpt("code_outer_border_pt", 2))
                )
                # Inner White Border (Stylish look from image)
                PDFExporter._draw_rounded_rectangle(
                    draw, [(x + pt_to_px(3), code_y + pt_to_px(3)), 
                           (x + code_w - pt_to_px(3), code_y + code_w - pt_to_px(3))],
                    radius=pt_to_px(lpt("code_inner_radius_pt", 4)),
                    outline='white', width=pt_to_px(lpt("code_inner_border_pt", 1))
                )
                bbox = f_code.getbbox(text)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                tx = x + (code_w - text_w) // 2 - bbox[0]
                ty = code_y + (code_w - text_h) // 2 - bbox[1]
                draw.text((tx, ty), text, font=f_code, fill='white')
            
            code_spacing = mm_to_px(lmm("code_spacing_mm", 1.5))
            draw_code_box(code_base_x, paper_code_1)
            draw_code_box(code_base_x + code_w + code_spacing, paper_code_2)
            draw_code_box(code_base_x + (code_w + code_spacing) * 2, paper_code_3)
            
            # 3. Time
            time_str = f"Time : {duration}"
            tw = draw.textlength(time_str, font=f_time)
            time_h = f_time.getbbox("Ag")[3] - f_time.getbbox("Ag")[1]
            time_y = y + (row2_h - time_h) // 2
            draw.text((PW - BORDER_MARGIN - tw - mm_to_px(lmm("time_right_pad_mm", 5)), time_y), time_str, font=f_time, fill='black')
            
            # --- SEPARATOR 2 ---
            y += row2_h + mm_to_px(2)
            draw.line([(BORDER_MARGIN, y), (PW - BORDER_MARGIN, y)], fill='black', width=pt_to_px(1))
            
            # --- ROW 3: Instructions | Constants | Marks ---
            y += mm_to_px(2)
            row3_h = mm_to_px(lmm("row3_h_mm", 17))
            
            # Pre-calc constants box position for centering instructions
            const_w = mm_to_px(lmm("const_w_mm", 66))
            const_x = (PW - const_w) // 2

            # 1. Instructions (Tamil) - centered vertically and horizontally in the left area
            instr_size = get_s("instructions", 20)
            line_gap = mm_to_px(2)
            line_h = qt_font_metrics(pref_font_name, instr_size, False, False)
            block_h = line_h * 2 + line_gap
            instr_y = y + (row3_h - block_h) // 2
            left_area_x = BORDER_MARGIN + mm_to_px(4)
            left_area_w = const_x - left_area_x - mm_to_px(2)
            line1 = "எல்லா வினாக்களுக்கும்"
            line2 = "விடை தருக."
            line1_w = qt_text_width(pref_font_name, instr_size, line1, False, False)
            line2_w = qt_text_width(pref_font_name, instr_size, line2, False, False)
            line1_x = left_area_x + max(0, (left_area_w - line1_w) // 2)
            line2_x = left_area_x + max(0, (left_area_w - line2_w) // 2)

            i1_img, i1_pos = PDFExporter._draw_text_qt(
                (line1_x, instr_y),
                line1,
                pref_font_name,
                instr_size,
                False
            )
            curr_page.paste(i1_img, i1_pos, i1_img)

            i2_img, i2_pos = PDFExporter._draw_text_qt(
                (line2_x, instr_y + line_h + line_gap),
                line2,
                pref_font_name,
                instr_size,
                False
            )
            curr_page.paste(i2_img, i2_pos, i2_img)

            # 2. Constants
            PDFExporter._draw_rounded_rectangle(
                draw, [(const_x, y), (const_x + const_w, y + row3_h)],
                radius=pt_to_px(lpt("const_radius_pt", 6)),
                outline='black', width=pt_to_px(lpt("const_border_pt", 1.5))
            )
            
            const_data = [
                ("அகில வாயு மாறிலி", "R", "8.314 J K⁻¹mol⁻¹"),
                ("அவகாதரோ மாறிலி", "Nₐ", "6.022 × 10²³ mol⁻¹"),
                ("பிளாங்கின் மாறிலி", "h", "6.626 × 10⁻³⁴ J s"),
                ("ஒளியின் வேகம்", "c", "3 × 10⁸ m s⁻¹")
            ]
            
            # Vertically center the block of constants within the box
            row_step = mm_to_px(lmm("const_row_step_mm", 3.6))
            line_h = qt_font_metrics(pref_font_name, get_s("constants", 18), False, False)
            total_block_h = line_h + row_step * (len(const_data) - 1)
            cy = y + (row3_h - total_block_h) // 2
            c_desc_x = const_x + mm_to_px(lmm("const_desc_x_mm", 3))
            c_sym_x = const_x + mm_to_px(lmm("const_sym_x_mm", 34))
            c_eq_x = const_x + mm_to_px(lmm("const_eq_x_mm", 39))
            c_val_x = const_x + mm_to_px(lmm("const_val_x_mm", 45))
            
            for desc, sym, val in const_data:
                # Use Qt Engine for perfect Tamil shaping
                d_img, d_pos = PDFExporter._draw_text_qt((c_desc_x, cy), desc, pref_font_name, get_s("constants", 18), False)
                curr_page.paste(d_img, d_pos, d_img)
                
                # Symbol (Italic Serif)
                s_img, s_pos = PDFExporter._draw_text_qt((c_sym_x, cy), sym, "Times New Roman", get_s("constants", 18), False, True)
                curr_page.paste(s_img, s_pos, s_img)

                # Equal Sign
                e_img, e_pos = PDFExporter._draw_text_qt((c_eq_x, cy), "=", "Arial", get_s("constants", 18), False)
                curr_page.paste(e_img, e_pos, e_img)
                
                # Value (Italic Serif)
                v_img, v_pos = PDFExporter._draw_text_qt((c_val_x, cy), val, "Times New Roman", get_s("constants", 18), False, True)
                curr_page.paste(v_img, v_pos, v_img)
                
                cy = cy + row_step
            
            # 3. Marks
            marks_box_w = mm_to_px(lmm("marks_box_w_mm", 16))
            marks_box_x = PW - BORDER_MARGIN - marks_box_w - mm_to_px(5)
            # Center "Marks" vertically and add a clean gap to the box
            marks_text = "Marks"
            marks_gap = mm_to_px(lmm("marks_gap_mm", 4))
            marks_h = f_marks.getbbox("Ag")[3] - f_marks.getbbox("Ag")[1]
            marks_y = y + (row3_h - marks_h) // 2
            marks_w = draw.textlength(marks_text, font=f_marks)
            marks_x = marks_box_x - marks_gap - marks_w
            draw.text((marks_x, marks_y), marks_text, font=f_marks, fill='black')
            PDFExporter._draw_rounded_rectangle(
                draw, [(marks_box_x, y), (marks_box_x + marks_box_w, y + row3_h)],
                radius=pt_to_px(lpt("marks_radius_pt", 6)),
                outline='black', width=pt_to_px(lpt("marks_border_pt", 1))
            )
            
            # --- LECTURER BAR ---
            y += row3_h + mm_to_px(4)
            draw.line([(BORDER_MARGIN, y), (PW - BORDER_MARGIN, y)], fill='black', width=pt_to_px(1))
            
            y_text = y + mm_to_px(2)
            
            name_w = draw.textlength(lecturer_name, font=f_lecturer)
            qual_w = draw.textlength(lecturer_qualification, font=f_lecturer_qual) 
            
            total_w = name_w + mm_to_px(3) + qual_w
            start_x = (PW - total_w) // 2
            
            draw.text((start_x, y_text), lecturer_name, font=f_lecturer, fill='black')
            draw.text((start_x + name_w + mm_to_px(3), y_text), lecturer_qualification, font=f_lecturer_qual, fill='black')
            
            y_bottom = y_text + mm_to_px(6)
            draw.line([(BORDER_MARGIN, y_bottom), (PW - BORDER_MARGIN, y_bottom)], fill='black', width=pt_to_px(1))

            # Name writing line area (above first question, below lecturer bar)
            def draw_dotted_underline(x1, x2, y_line):
                start_x = int(x1)
                end_x = int(x2)
                if end_x <= start_x:
                    return
                dot_len = max(1, pt_to_px(lpt("name_dot_len_pt", 1.2)))
                dot_step = max(dot_len + 1, pt_to_px(lpt("name_dot_gap_pt", 3.2)))
                for dx in range(start_x, end_x, dot_step):
                    draw.line(
                        [(dx, y_line), (min(dx + dot_len, end_x), y_line)],
                        fill='black',
                        width=max(1, pt_to_px(0.8))
                    )

            name_label = "NAME :"
            name_h = f_time.getbbox("Ag")[3] - f_time.getbbox("Ag")[1]
            name_x = BORDER_MARGIN + mm_to_px(lmm("name_area_left_pad_mm", 12))
            name_y = y_bottom + mm_to_px(lmm("name_area_top_pad_mm", 2.2))
            draw.text((name_x, name_y), name_label, font=f_time, fill='black')

            name_label_w = draw.textlength(name_label, font=f_time)
            dotted_start_x = name_x + name_label_w + mm_to_px(lmm("name_label_gap_mm", 2))
            dotted_end_x = PW - BORDER_MARGIN - mm_to_px(lmm("name_area_right_pad_mm", 8))
            dotted_y = name_y + name_h - pt_to_px(1.5)
            if dotted_end_x > dotted_start_x + mm_to_px(8):
                draw_dotted_underline(dotted_start_x, dotted_end_x, dotted_y)

            # Separator under NAME row (same visual style as lecturer underline)
            name_sep_y = name_y + name_h + mm_to_px(lmm("name_sep_gap_mm", 1.8))
            draw.line([(BORDER_MARGIN, name_sep_y), (PW - BORDER_MARGIN, name_sep_y)], fill='black', width=pt_to_px(1))
            
            # --- QUESTIONS LOOP ---
            y_cursor = name_sep_y + mm_to_px(lmm("name_to_q_gap_mm", 2.8))
            
            Q_NUM_X = BORDER_MARGIN + mm_to_px(8)
            Q_CONTENT_X = BORDER_MARGIN + mm_to_px(20)
            Q_MAX_W = PW - Q_CONTENT_X - BORDER_MARGIN - mm_to_px(5)
            question_gap_px = mm_to_px(float(config.get("layout", {}).get("question_gap_mm", 8)))
            question_gap_px = max(mm_to_px(2), question_gap_px)

            question_order = str(config.get("question_order", "top_to_bottom")).lower()
            ordered_questions = list(questions)
            if config.get("reverse_questions") or question_order in ("bottom_to_top", "reverse", "descending"):
                ordered_questions.reverse()
            
            start_q = int(config.get("start_question_number", 1) or 1)
            q_style = str(config.get("question_number_style", "zero_padded")).lower()
            q_counter = start_q
            for i, q_data in enumerate(ordered_questions):
                img_path = q_data.get("img_path")
                if not img_path or not os.path.exists(img_path):
                    continue
                
                img_q = Image.open(img_path)
                orig_w, orig_h = img_q.size
                scale = min(1.0, Q_MAX_W / orig_w)
                target_w = int(orig_w * scale)
                target_h = int(orig_h * scale)
                
                footer_h = mm_to_px(15)
                if y_cursor + target_h > PH - BORDER_MARGIN - footer_h:
                    PDFExporter._draw_footer(
                        draw,
                        PW,
                        PH,
                        BORDER_MARGIN,
                        lecturer_name,
                        page_num,
                        f_footer,
                        footer_quote,
                        layout,
                        bool(config.get("show_page_numbers", True)),
                    )
                    pages.append(curr_page)
                    page_num += 1
                    curr_page = Image.new('RGB', (PW, PH), 'white')
                    draw = ImageDraw.Draw(curr_page)
                    PDFExporter._draw_rounded_rectangle(
                        draw,
                        [(BORDER_MARGIN, BORDER_MARGIN), (PW - BORDER_MARGIN, PH - BORDER_MARGIN)],
                        radius=BORDER_RADIUS, outline='black', width=BORDER_WIDTH
                    )
                    y_cursor = BORDER_MARGIN + mm_to_px(10)
                
                if bool(q_data.get("show_number", True)):
                    if q_style in ("plain", "numeric"):
                        q_num_str = f"{q_counter}."
                    elif q_style in ("q_prefix", "q"):
                        q_num_str = f"Q{q_counter}."
                    else:
                        q_num_str = f"{q_counter:02d}."
                    draw.text((Q_NUM_X, y_cursor), q_num_str, font=f_question_num, fill='black')
                    q_counter += 1
                
                if scale != 1.0:
                    img_q = img_q.resize((target_w, target_h), Image.Resampling.LANCZOS)
                curr_page.paste(img_q, (Q_CONTENT_X, y_cursor))
                y_cursor += target_h + question_gap_px
                
            PDFExporter._draw_footer(
                draw,
                PW,
                PH,
                BORDER_MARGIN,
                lecturer_name,
                page_num,
                f_footer,
                footer_quote,
                layout,
                bool(config.get("show_page_numbers", True)),
            )
            pages.append(curr_page)
            
            if pages:
                pages[0].save(output_path, "PDF", resolution=300.0, save_all=True, append_images=pages[1:])
                return True
                
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return False

    @staticmethod
    def _draw_footer(draw, W, H, margin, lecturer_name, page_num, font, quote, layout=None, show_page_number=True):
        """Draws the specific footer from reference"""
        def pt_to_px_local(pt):
            return int(pt * 300 / 72)

        layout = layout or {}
        def lpt(key, default): return float(layout.get(key, default))

        text_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
        text_y = H - margin - text_h - pt_to_px_local(lpt("footer_text_offset_pt", 3))
        line_y = text_y - pt_to_px_local(lpt("footer_line_gap_pt", 2))
        draw.line([(margin, line_y), (W - margin, line_y)], fill='black', width=pt_to_px_local(1))

        side_pad = pt_to_px_local(lpt("footer_side_pad_pt", 10))
        left_x = margin + side_pad
        draw.text((left_x, text_y), lecturer_name, font=font, fill='black')

        if show_page_number:
            p_text = str(page_num)
            pw = draw.textlength(p_text, font=font)
            draw.text(((W - pw) // 2, text_y), p_text, font=font, fill='black')

        qw = draw.textlength(quote, font=font)
        right_x = W - margin - side_pad - qw
        draw.text((right_x, text_y), quote, font=font, fill='black')

    @staticmethod
    def _draw_rounded_rectangle(draw, coords, radius=20, fill=None, outline=None, width=1):
        x1, y1 = coords[0]
        x2, y2 = coords[1]
        draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=fill, outline=outline, width=width)

    @staticmethod
    def generate_exam_docx(questions, output_path, title="Exam Paper"):
        doc = Document()
        doc.save(output_path)
        return True

    @staticmethod
    def generate_answer_key_pdf(questions, output_path, title="Answer Key"):
        return True
