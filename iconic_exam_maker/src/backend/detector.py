import fitz
import cv2
import numpy as np
import re

def merge_overlapping_boxes(boxes, iou_threshold=0.3):
    """
    Merges boxes that overlap significantly.
    boxes: list of dicts with 'bbox' (x1, y1, x2, y2) and other keys.
    """
    if not boxes:
        return []

    def get_iou(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    # Grouping logic
    merged = []
    already_merged = set()

    for i in range(len(boxes)):
        if i in already_merged:
            continue
        
        current_group = [boxes[i]]
        already_merged.add(i)
        
        # Look for others to merge into this group
        for j in range(i + 1, len(boxes)):
            if j in already_merged:
                continue
            
            # Check overlap with any in current group
            for member in current_group:
                if get_iou(member["bbox"], boxes[j]["bbox"]) > iou_threshold:
                    current_group.append(boxes[j])
                    already_merged.add(j)
                    break
        
        # Merge the group
        if len(current_group) == 1:
            merged.append(current_group[0])
        else:
            # Combine bboxes
            bxs = [g["bbox"] for g in current_group]
            x1 = min(b[0] for b in bxs)
            y1 = min(b[1] for b in bxs)
            x2 = max(b[2] for b in bxs)
            y2 = max(b[3] for b in bxs)
            
            # Determine label and type (prefer mcq over others)
            types = [g["type"] for g in current_group]
            best_type = "mcq" if "mcq" in types else current_group[0]["type"]
            best_label = next((g["label"] for g in current_group if g["type"] == best_type), current_group[0]["label"])
            
            merged.append({
                "bbox": (x1, y1, x2, y2),
                "label": best_label,
                "type": best_type
            })
            
    return merged

class MCQDetector:
    """Specialized detector for MCQs with answer options"""
    def __init__(self, doc):
        self.doc = doc
    
    def detect_mcqs_on_page(self, page_index):
        """Detects MCQ blocks (question + options + answer)"""
        if not self.doc: return []
        page = self.doc[page_index]
        blocks = page.get_text("blocks")
        
        if not blocks:
            return self._detect_mcq_visual(page)
        
        page_height = page.rect.height
        page_width = page.rect.width
        
        mcq_candidates = []
        
        for b in blocks:
            text = b[4].strip()
            x, y = b[0], b[1]
            
            if y < page_height * 0.15:
                continue
            
            if re.match(r"^\d{1,2}\.$", text):
                num_match = re.search(r"^(\d{1,2})", text)
                if num_match:
                    num = num_match.group(1)
                    mcq_candidates.append({"y": y, "x": x, "number": num})
        
        mcq_candidates.sort(key=lambda c: c["y"])
        
        crops = []
        for i, curr in enumerate(mcq_candidates):
            y1 = max(0, curr["y"] - 15)
            if i < len(mcq_candidates) - 1:
                y2 = mcq_candidates[i + 1]["y"] - 20
            else:
                y2 = page_height - 80
            
            x1, x2 = 25, page_width - 25
            crops.append({
                "bbox": (x1, y1, x2, y2),
                "label": f"MCQ_{curr['number']}",
                "type": "mcq"
            })
        
        if not crops:
             return self._detect_mcq_visual(page)

        return crops
    
    def _detect_mcq_visual(self, page):
        scale = 3
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        h, w = gray.shape
        # Mask borders
        cv2.rectangle(gray, (0, 0), (w, int(h * 0.15)), 255, -1)
        cv2.rectangle(gray, (0, int(h * 0.92)), (w, h), 255, -1)
        cv2.rectangle(gray, (0, 0), (int(w * 0.03), h), 255, -1)
        cv2.rectangle(gray, (int(w * 0.97), 0), (w, h), 255, -1)
        
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (100, 40))
        dilated = cv2.dilate(thresh, kernel, iterations=4)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw > 200 and ch > 100 and ch < h * 0.4:
                boxes.append({
                    "bbox": (x/scale, y/scale, (x+cw)/scale, (y+ch)/scale),
                    "label": f"MCQ_{len(boxes)+1}",
                    "type": "mcq"
                })
        
        boxes.sort(key=lambda b: b["bbox"][1])
        return boxes

class AdvancedQuestionDetector:
    """Robust Scoring-Based Question Detector"""
    def __init__(self, doc):
        self.doc = doc

    def detect_questions_on_page(self, page_index):
        if not self.doc: return []
        page = self.doc[page_index]
        blocks = page.get_text("blocks")
        
        if not blocks:
            return self._detect_by_image_fallback(page)

        x_coords = [b[0] for b in blocks if b[0] < page.rect.width / 2]
        if not x_coords:
            return []
            
        x_bins = {}
        for x in x_coords:
            bin_x = round(x / 5) * 5
            x_bins[bin_x] = x_bins.get(bin_x, 0) + 1
            
        sorted_bins = sorted(x_bins.items()) 
        primary_margin = sorted_bins[0][0]
        most_popular = max(x_bins.items(), key=lambda item: item[1])
        if most_popular[1] > 3: 
             primary_margin = most_popular[0]
             
        candidates = []
        page_height = page.rect.height
        
        for b in blocks:
            text = b[4].strip()
            x, y = b[0], b[1]
            
            if y < page_height * 0.15: continue
            
            score = 0
            if abs(x - primary_margin) <= 15: score += 50
            elif x > primary_margin + 20: score -= 100
            
            if re.match(r"^\d+\.", text): score += 40
            elif re.match(r"^Q(uestion)?\s*\d+", text, re.IGNORECASE): score += 40
                
            if re.match(r"^\d+\)", text): score -= 50
            if re.match(r"^\(\d+\)", text): score -= 50
            if re.match(r"^[A-E]\.", text): score -= 100
            
            if len(text) < 4 and not re.match(r"^\d+\.$", text): score -= 20
                
            if score >= 60:
                candidates.append({"y": y, "x": x, "text": text, "score": score})

        candidates.sort(key=lambda c: c["y"])
        
        crops = []
        page_width = page.rect.width
        
        for i in range(len(candidates)):
            curr = candidates[i]
            y1 = max(0, curr["y"] - 10)
            if i < len(candidates) - 1:
                next_q = candidates[i+1]
                y2 = next_q["y"] - 15
            else:
                y2 = page_height - 50 
                
            q_num_match = re.match(r"(\d+)", curr["text"])
            label = f"Q{q_num_match.group(1)}" if q_num_match else f"Q_Auto_{i+1}"
            
            crops.append({
                "bbox": (25, y1, page_width - 25, y2),
                "label": label,
                "type": "standard"
            })
            
        if not crops:
            return self._detect_by_image_fallback(page)
            
        return crops

    def _detect_by_image_fallback(self, page):
        scale_x, scale_y = 2, 2
        pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        gray = cv2.cvtColor(img_data, cv2.COLOR_RGB2GRAY)
        
        h, w = gray.shape
        cv2.rectangle(gray, (0, 0), (w, int(h * 0.18)), (255), -1)
        cv2.rectangle(gray, (0, int(h * 0.90)), (w, h), (255), -1)
        cv2.rectangle(gray, (0, 0), (int(w * 0.05), h), (255), -1)
        cv2.rectangle(gray, (int(w * 0.95), 0), (w, h), (255), -1)

        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 30)) 
        dilated = cv2.dilate(thresh, kernel, iterations=3)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if ch > h * 0.6: continue
            if cw > 100 and ch > 50: 
                boxes.append({
                    "bbox": (x/scale_x, y/scale_y, (x+cw)/scale_x, (y+ch)/scale_y),
                    "label": f"Q_Img_{len(boxes)+1}",
                    "type": "visual"
                })
        
        boxes.sort(key=lambda b: b["bbox"][1])
        return boxes
