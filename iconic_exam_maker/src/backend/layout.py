from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

class FWCLayoutEngine:
    """
    OFFICIAL EXAM LAYOUT ENGINE (FWC STYLE)
    Replicates the 'National Field Work Centre' layout.
    Decoupled from UI.
    """
    def __init__(self, output_dir="exam_papers"):
        self.output_dir = output_dir
        # Configurable constants could go here
        
    def generate_paper(self, questions, metadata):
        """
        questions: List of absolute file paths to question images
        metadata: Dict containing {
            "subject": str,
            "title": str,
            "duration": str,
            "paper_codes": [code1, code2, code3],
            "logo_path": str (optional)
        }
        """
        # Unpack Metadata
        subject = metadata.get("subject", "PHYSICS")
        exam_title = metadata.get("title", "Term Examination")
        duration = metadata.get("duration", "One Hour")
        codes = metadata.get("paper_codes", ["01", "T", "I"])
        logo_path = metadata.get("logo_path", None)
        
        # A4 @ 300 DPI
        PW, PH = 2480, 3508 
        
        # KEY LAYOUT CONSTANTS
        MARGIN_LEFT = 120
        MARGIN_RIGHT = 120
        HEADER_TOP = 100 
        
        # QUESTION GRID
        Q_NUM_X = 140         
        Q_CONTENT_X = 240     
        Q_MAX_W = PW - Q_CONTENT_X - MARGIN_RIGHT 
        
        # FONTS
        try:
            f_inst_main = ImageFont.truetype("timesbd.ttf", 45) 
            f_inst_sub = ImageFont.truetype("times.ttf", 30)    
            f_title = ImageFont.truetype("timesbd.ttf", 35)     
            f_subject = ImageFont.truetype("timesbd.ttf", 45)   
            f_box_text = ImageFont.truetype("timesbd.ttf", 28)  
            f_q_num = ImageFont.truetype("timesbd.ttf", 40)     
            f_page = ImageFont.truetype("times.ttf", 25)
            f_part = ImageFont.truetype("timesbd.ttf", 35)      
        except OSError as e:
            print(f"[layout.py] Font loading failed: {e}. Falling back to default font.")
            f_inst_main = f_inst_sub = f_title = f_subject = f_box_text = f_q_num = f_page = f_part = ImageFont.load_default()

        pages = []
        page_num = 1
        
        try:
            # --- PAGE 1 SETUP ---
            curr_page = Image.new('RGB', (PW, PH), 'white')
            draw = ImageDraw.Draw(curr_page)
            self._draw_page_border(draw, PW, PH)
            
            # --- HEADER GENERATION ---
            y = HEADER_TOP
            
            # 1. LOGO
            logo_size = 150 
            if logo_path and os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                    curr_page.paste(logo, (MARGIN_LEFT + 10, y))
                except Exception as e: 
                    print(f"Error loading logo: {e}")
            
            # 2. INSTITUTE TEXT
            center_x = PW // 2
            txt_inst = "Conducted by Field Work Centre, Thondaimanaru"
            w = draw.textlength(txt_inst, font=f_inst_main)
            draw.text((center_x - w/2, y + 10), txt_inst, font=f_inst_main, fill='black')
            
            y += 65
            txt_title = f"{exam_title} - 2026"
            w = draw.textlength(txt_title, font=f_title)
            draw.text((center_x - w/2, y), txt_title, font=f_title, fill='black')
            
            # 3. BOX GRID
            y += 80
            box_h_row1 = 60
            box_h_row2 = 60
            
            w_dur = 200
            w_grade = 200
            w_code = 70
            
            right_w = w_dur + w_grade + (w_code * 3)
            right_start_x = PW - MARGIN_RIGHT - right_w - 10
            
            rt_x = right_start_x
            rt_y = y
            
            total_h = box_h_row1 + box_h_row2
            draw.rounded_rectangle([(rt_x, rt_y), (rt_x + right_w, rt_y + total_h)], radius=15, outline='black', width=2)
            
            # Dividers
            line_x = rt_x + w_dur
            draw.line([(line_x, rt_y), (line_x, rt_y + total_h)], fill='black', width=2)
            line_x += w_grade
            draw.line([(line_x, rt_y), (line_x, rt_y + total_h)], fill='black', width=2)
            line_x += w_code
            draw.line([(line_x, rt_y), (line_x, rt_y + total_h)], fill='black', width=2)
            line_x += w_code
            draw.line([(line_x, rt_y), (line_x, rt_y + total_h)], fill='black', width=2)
            
            draw.line([(rt_x, rt_y + box_h_row1), (rt_x + right_w, rt_y + box_h_row1)], fill='black', width=2)
            
            def draw_box_txt(txt, bx, by, bw, bh):
                if not txt: return
                tw = draw.textlength(txt, font=f_box_text)
                draw.text((bx + bw/2 - tw/2, by + bh/2 - 12), txt, font=f_box_text, fill='black')
                
            draw_box_txt("Duration", rt_x, rt_y, w_dur, box_h_row1)
            draw_box_txt("Grade", rt_x + w_dur, rt_y, w_grade, box_h_row1)
            draw_box_txt("Code", rt_x + w_dur + w_grade, rt_y, w_code*3, box_h_row1)
            
            draw_box_txt(duration, rt_x, rt_y + box_h_row1, w_dur, box_h_row2)
            draw_box_txt("13", rt_x + w_dur, rt_y + box_h_row1, w_grade, box_h_row2)
            
            cx = rt_x + w_dur + w_grade
            p1 = codes[0] if len(codes) > 0 else "01"
            p2 = codes[1] if len(codes) > 1 else "T"
            p3 = codes[2] if len(codes) > 2 else "I"
            
            draw_box_txt(p1, cx, rt_y + box_h_row1, w_code, box_h_row2)
            cx += w_code
            draw_box_txt(p2, cx, rt_y + box_h_row1, w_code, box_h_row2)
            cx += w_code
            draw_box_txt(p3, cx, rt_y + box_h_row1, w_code, box_h_row2)
            
            # LEFT SIDE
            subj_x = MARGIN_LEFT + 20
            subj_txt = f"{subject.upper()}  I"
            draw.text((subj_x, rt_y + 30), subj_txt, font=f_subject, fill='black')
            draw.text((subj_x, rt_y + 85), "Marks: 100", font=f_box_text, fill='black')

            # PART HEADER
            y = rt_y + total_h + 30
            part_txt = "PART - I"
            site_w = draw.textlength(part_txt, font=f_part)
            draw.text((center_x - site_w/2, y), part_txt, font=f_part, fill='black')
             
            y += 50
            draw.line([(MARGIN_LEFT, y), (PW - MARGIN_RIGHT, y)], fill='black', width=2)
            y += 40

            # --- QUESTIONS ---
            for i, q_path in enumerate(questions):
                if not q_path or not os.path.exists(q_path): continue
                img_q = Image.open(q_path)
                
                orig_w, orig_h = img_q.size
                scale = min(1.0, Q_MAX_W / orig_w)
                if orig_w < 500: scale = 1.0 
                
                target_w = int(orig_w * scale)
                target_h = int(orig_h * scale)
                
                if scale != 1.0:
                    img_q = img_q.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    
                needed_h = target_h + 60
                if y + needed_h > PH - 150:
                    draw.text((PW//2, PH - 80), f"- {page_num} -", font=f_page, fill='black', anchor="mm")
                    pages.append(curr_page)
                    page_num += 1
                    curr_page = Image.new('RGB', (PW, PH), 'white')
                    draw = ImageDraw.Draw(curr_page)
                    self._draw_page_border(draw, PW, PH)
                    y = 150
                
                draw.text((Q_NUM_X, y), f"{i+1}.", font=f_q_num, fill='black')
                curr_page.paste(img_q, (Q_CONTENT_X, y + 10))
                y += target_h + 50
            
            draw.text((PW//2, PH - 80), f"- {page_num} -", font=f_page, fill='black', anchor="mm")
            pages.append(curr_page)

            # Save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(self.output_dir, exist_ok=True)
            out_path = os.path.join(self.output_dir, f"Exam_Paper_{timestamp}.pdf")
            
            pages[0].save(out_path, "PDF", resolution=300.0, save_all=True, append_images=pages[1:])
            return out_path
            
        except Exception as e:
            import traceback
            print("Layout Error:", traceback.format_exc())
            return None

    def _draw_page_border(self, draw, page_width, page_height):
        """Official exam-style border (Double Line: Thick Outer, Thin Inner)"""
        outer_pad = 70
        draw.rectangle(
            [(outer_pad, outer_pad), (page_width - outer_pad, page_height - outer_pad)],
            outline="black", width=6
        )
        inner_pad = 90
        draw.rectangle(
            [(inner_pad, inner_pad), (page_width - inner_pad, page_height - inner_pad)],
            outline="black", width=2
        )
