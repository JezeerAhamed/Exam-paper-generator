from __future__ import annotations

from PySide6.QtCore import QThread, Signal
import fitz
import os
import traceback
from PIL import Image
from src.backend.detector import AdvancedQuestionDetector, MCQDetector, merge_overlapping_boxes
from src.backend.image_processor import clean_image, auto_enhance


class DetectionWorker(QThread):
    progress_update = Signal(int, str)  # value, message
    finished = Signal(list)  # List of processed data blocks
    error = Signal(str)

    def __init__(self, file_paths: list[str], enhance_images: bool = True) -> None:
        super().__init__()
        self.file_paths = file_paths
        self.is_running = True
        self.enhance_images = enhance_images  # New: enable/disable image enhancement

    def run(self):
        try:
            results = []
            
            # Pre-calculate total pages for progress
            total_pages_across_all = 0
            file_page_counts = []
            for path in self.file_paths:
                try:
                    d = fitz.open(path)
                    count = len(d)
                    total_pages_across_all += count
                    file_page_counts.append(count)
                    d.close()
                except (FileNotFoundError, PermissionError) as e:
                    print(f"[workers.py] Cannot open file {path}: {e}")
                    file_page_counts.append(0)
                except Exception as e:
                    print(f"[workers.py] Unexpected error opening {path}: {e}")
                    file_page_counts.append(0)

            pages_processed = 0
            
            for f_idx, path in enumerate(self.file_paths):
                if not self.is_running: break
                
                fname = os.path.basename(path)
                
                try:
                    doc = fitz.open(path)
                    detector = AdvancedQuestionDetector(doc)
                    mcq_detector = MCQDetector(doc)
                    
                    total_pages = len(doc)
                    file_data = {"path": path, "pages": []}
                    
                    for p_idx in range(total_pages):
                        if not self.is_running: break
                        
                        # Update Progress
                        msg = f"Processing '{fname}' (Page {p_idx+1}/{total_pages})..."
                        overall_progress = int((pages_processed / total_pages_across_all) * 100) if total_pages_across_all > 0 else 0
                        self.progress_update.emit(overall_progress, msg)
                        
                        # Detect
                        std_questions = detector.detect_questions_on_page(p_idx)
                        mcqs = mcq_detector.detect_mcqs_on_page(p_idx)
                        merged_questions = merge_overlapping_boxes(std_questions + mcqs)
                        
                        # NEW: Enhance detected question images if enabled
                        if self.enhance_images and merged_questions:
                            page = doc[p_idx]
                            for q_data in merged_questions:
                                try:
                                    # Extract question region as image
                                    bbox = q_data.get('bbox')
                                    if bbox:
                                        x1, y1, x2, y2 = bbox
                                        rect = fitz.Rect(x1, y1, x2, y2)
                                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                                        
                                        # Convert to PIL Image
                                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                        
                                        # Apply light enhancement (not aggressive to preserve quality)
                                        enhanced_img = auto_enhance(img, aggressive=False)
                                        
                                        # Store enhanced image data in question metadata
                                        q_data['enhanced'] = True
                                except Exception as e:
                                    print(f"Warning: Could not enhance question: {e}")
                                    q_data['enhanced'] = False
                        
                        file_data["pages"].append({
                            "page_num": p_idx + 1,
                            "questions": merged_questions
                        })
                        
                        pages_processed += 1
                    
                    results.append(file_data)
                    doc.close()
                    
                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"Detection failed for {fname}: {tb}")
                    self.error.emit(f"{fname}: {str(e)}")
                    # Continue with next file
                    pages_processed += file_page_counts[f_idx]
            
            if self.is_running:
                self.progress_update.emit(100, "Finalizing...")
                self.finished.emit(results)
                
        except Exception as e:
            print(traceback.format_exc())
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False
