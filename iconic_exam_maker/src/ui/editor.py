import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QGraphicsView, QGraphicsScene, QSplitter, 
                               QPushButton, QGraphicsRectItem, QGraphicsPixmapItem, 
                               QGraphicsItem, QFrame, QGroupBox, QFormLayout, 
                               QLineEdit, QSpinBox, QMessageBox, QSlider, QDialog,
                               QProgressDialog, QApplication)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QRect, QTimer
from PySide6.QtGui import QImage, QPixmap, QPen, QColor, QBrush, QPainter, QCursor, QTransform
import os
from src.utils.converter import PDFToImageConverter
from src.backend.yolo_detector import YOLOQuestionDetector, load_ai_detection_config

DEFAULT_OPEN_ZOOM = 0.68

class CropHandle(QGraphicsRectItem):
    """Small handle for resizing the crop rect."""
    def __init__(self, position_flags, parent):
        super().__init__(-4, -4, 8, 8, parent)
        self.position_flags = position_flags
        self.setBrush(QBrush(QColor("#FF3333")))
        self.setPen(QPen(QColor("#7A0000"), 1))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#FFFFFF")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#FF3333")))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        new_pos = self.parentItem().mapFromScene(event.scenePos())
        self.parentItem().interactive_resize(self.position_flags, new_pos)
        event.accept()

class ManualCropRect(QGraphicsRectItem):
    """A resizable, draggable rectangle for manual cropping."""
    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.setPen(QPen(QColor("#FF0000"), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 0, 0, 20)))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.handles = []
        # TL, T, TR, R, BR, B, BL, L
        handle_configs = [
            (True, False, True, False), (True, False, False, False),
            (True, False, False, True), (False, False, False, True),
            (False, True, False, True), (False, True, False, False),
            (False, True, True, False), (False, False, True, False)
        ]
        for cfg in handle_configs:
            self.handles.append(CropHandle(cfg, self))
        self.update_handles()

    def update_handles(self):
        r = self.rect()
        l, t, r_edge, b = r.left(), r.top(), r.right(), r.bottom()
        w, h = r.width(), r.height()
        mx, my = l + w/2, t + h/2
        positions = [(l, t), (mx, t), (r_edge, t), (r_edge, my), (r_edge, b), (mx, b), (l, b), (l, my)]
        for handle, pos in zip(self.handles, positions):
            handle.setPos(pos[0], pos[1])

    def interactive_resize(self, flags, mouse_pos):
        r = self.rect()
        l, t, w, h = r.x(), r.y(), r.width(), r.height()
        right, bottom = l + w, t + h
        is_t, is_b, is_l, is_r = flags
        if is_t: 
            t = mouse_pos.y()
            h = bottom - t
        elif is_b: h = mouse_pos.y() - t
        if is_l:
            l = mouse_pos.x()
            w = right - l
        elif is_r: w = mouse_pos.x() - l
        self.setRect(QRectF(l, t, w, h).normalized())
        self.update_handles()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self.update_handles()
        return super().itemChange(change, value)

class CanvasView(QGraphicsView):
    """Support smooth zoom, panning, and crop drawing."""
    crop_finished = Signal(QRectF)
    zoom_changed = Signal(float)

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Changed from #2C3E50 to standard Acrobat document background
        self.setBackgroundBrush(QBrush(QColor("#E6E6E6")))
        
        self._is_panning = False
        self._is_drawing = False
        self._start_pos = None
        self._current_rect = None
        self._space_pressed = False
        self._zoom = 1.0

    def set_zoom(self, zoom):
        zoom = max(0.1, min(3.0, zoom))
        self._zoom = zoom
        self.setTransform(QTransform().scale(self._zoom, self._zoom))
        self.zoom_changed.emit(self._zoom)

    def get_zoom(self):
        return self._zoom

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.set_zoom(self._zoom * zoom_in_factor)
            else:
                self.set_zoom(self._zoom * zoom_out_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self._space_pressed or event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked an existing handle or rect
            item = self.itemAt(event.pos())
            if isinstance(item, (ManualCropRect, CropHandle)):
                super().mousePressEvent(event)
                return

            self._is_drawing = True
            self._start_pos = self.mapToScene(event.pos())
            if self._current_rect:
                try:
                    if self._current_rect.scene() is not None:
                        self.scene().removeItem(self._current_rect)
                except RuntimeError:
                    # Stale wrapper after scene/page reset; ignore and recreate.
                    pass
                finally:
                    self._current_rect = None
            self._current_rect = ManualCropRect(self._start_pos.x(), self._start_pos.y(), 0, 0)
            self.scene().addItem(self._current_rect)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        elif self._is_drawing and self._current_rect:
            try:
                curr_pos = self.mapToScene(event.pos())
                rect = QRectF(self._start_pos, curr_pos).normalized()
                self._current_rect.setRect(rect)
                event.accept()
            except RuntimeError:
                self._current_rect = None
                self._is_drawing = False
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self._is_panning):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
            self._is_drawing = False
            if self._current_rect:
                try:
                    if self._current_rect.rect().width() > 5:
                        # Select the new rect
                        self._current_rect.setSelected(True)
                        self.crop_finished.emit(self._current_rect.rect())
                except RuntimeError:
                    self._current_rect = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().keyReleaseEvent(event)

class Editor(QWidget):
    def __init__(self, project_manager):
        super().__init__()
        self.pm = project_manager
        self.current_pdf = None
        self.pdf_files = []
        self.current_pdf_index = -1
        self.current_page = 0
        self.total_pages = 0
        self.pix_item = None
        self.state_path = os.path.join("config", "editor_state.json")
        self.page_cache = {}
        self.cache_limit = 5
        self.yolo_detector = None
        self._ai_enabled = False
        self._ai_model_path = ""
        self._ai_confidence = 0.25
        self.default_open_zoom = DEFAULT_OPEN_ZOOM
        self.ai_crop_rects = []
        self._init_yolo_detector()
        self.init_ui()


    def _init_yolo_detector(self):
        '''Load AI detection settings (defer model loading until needed).'''
        try:
            ai_config, _config_path = load_ai_detection_config()
            if not ai_config:
                self._ai_enabled = False
                return

            self._ai_enabled = bool(ai_config.get("enabled", False))
            self._ai_model_path = ai_config.get("model_path", "")
            self._ai_confidence = float(ai_config.get("confidence_threshold", 0.25))
        except Exception as e:
            print(f"Error initializing YOLO detector: {e}")
            self._ai_enabled = False

    def _ensure_yolo_detector(self):
        """Create detector on demand, only when AI feature is actually used."""
        if not self._ai_enabled:
            return False

        if self.yolo_detector is None:
            self.yolo_detector = YOLOQuestionDetector(
                model_path=self._ai_model_path,
                confidence_threshold=self._ai_confidence,
            )

        return bool(self.yolo_detector and self.yolo_detector.is_available())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #E2E8F0;")
        tb_layout = QHBoxLayout(toolbar)
        
        self.lbl_info = QLabel("Pick a PDF to start...")
        self.lbl_info.setStyleSheet("font-weight: 600; color: #4A5568;")
        tb_layout.addWidget(self.lbl_info)
        
        tb_layout.addStretch()
        
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(40, 40)
        btn_zoom_out.clicked.connect(lambda: self.view.set_zoom(self.view.get_zoom() * 0.8))
        tb_layout.addWidget(btn_zoom_out)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(40, 40)
        btn_zoom_in.clicked.connect(lambda: self.view.set_zoom(self.view.get_zoom() * 1.25))
        tb_layout.addWidget(btn_zoom_in)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_layout.addWidget(self.zoom_label)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(140)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider)
        tb_layout.addWidget(self.zoom_slider)
        
        btn_undo = QPushButton("Undo Crop")
        btn_undo.setFixedSize(100, 40)
        btn_undo.clicked.connect(self.discard_crop)
        tb_layout.addWidget(btn_undo)
        
        # AI Auto Detect Button
        self.btn_ai_detect = QPushButton("AI Detect + Crop")
        self.btn_ai_detect.setFixedSize(145, 40)
        self.btn_ai_detect.setToolTip("Detect questions with YOLO and auto-crop")
        self.btn_ai_detect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ai_detect.setStyleSheet('''
            QPushButton {
                background-color: #1473E6; /* Acrobat Blue */
                color: white;
                border: none;
                border-radius: 4px; /* Flat layout */
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0D66D0;
            }
            QPushButton:disabled {
                background-color: #B5D4FF;
                color: #FFFFFF;
            }
        ''')
        self.btn_ai_detect.clicked.connect(self.run_ai_detection)
        tb_layout.addWidget(self.btn_ai_detect)
        
        tb_layout.addSpacing(20)
        
        self.btn_prev = QPushButton("⇠ Prev")
        self.btn_prev.setFixedSize(100, 40)
        self.btn_prev.clicked.connect(self.prev_page)
        tb_layout.addWidget(self.btn_prev)
        
        self.btn_next = QPushButton("Next ⇢")
        self.btn_next.setObjectName("primary")
        self.btn_next.setFixedSize(100, 40)
        self.btn_next.clicked.connect(self.next_page)
        tb_layout.addWidget(self.btn_next)
        
        layout.addWidget(toolbar)

        # 2. Main Content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Canvas
        self.scene = QGraphicsScene()
        self.view = CanvasView(self.scene)
        self.view.crop_finished.connect(self.on_crop_defined)
        self.view.zoom_changed.connect(self.on_zoom_changed)
        splitter.addWidget(self.view)
        
        # Confirmation Panel (Hidden by default)
        self.confirm_panel = QWidget()
        self.confirm_panel.setFixedWidth(300)
        self.confirm_panel.setStyleSheet("background-color: #F8F8F8; border-left: 1px solid #D6D6D6;")
        cp_layout = QVBoxLayout(self.confirm_panel)
        cp_layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_preview = QLabel("CROP PREVIEW")
        lbl_preview.setStyleSheet("font-weight: 800; font-size: 11px; color: #718096;")
        cp_layout.addWidget(lbl_preview)
        
        self.preview_img = QLabel()
        self.preview_img.setFixedSize(260, 260)
        self.preview_img.setStyleSheet("background-color: white; border: 1px solid #C4C4C4; border-radius: 2px;")
        self.preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cp_layout.addWidget(self.preview_img)
        
        self.btn_preview_full = QPushButton("Open Full Preview")
        self.btn_preview_full.setFixedHeight(36)
        self.btn_preview_full.clicked.connect(self.show_full_preview)
        cp_layout.addWidget(self.btn_preview_full)
        
        self.meta_group = QGroupBox("PROPERTIES")
        self.meta_group.setStyleSheet("font-weight: 800; font-size: 11px; color: #718096;")
        meta_form = QFormLayout(self.meta_group)
        
        self.edit_marks = QSpinBox()
        self.edit_marks.setRange(0, 100)
        meta_form.addRow("Marks:", self.edit_marks)
        
        self.edit_topic = QLineEdit()
        self.edit_topic.setPlaceholderText("Chapter/Topic")
        meta_form.addRow("Topic:", self.edit_topic)
        
        cp_layout.addWidget(self.meta_group)
        cp_layout.addStretch()
        
        self.btn_save = QPushButton("✅ SAVE CROP (Enter)")
        self.btn_save.setObjectName("success")
        self.btn_save.setFixedHeight(50)
        self.btn_save.clicked.connect(self.save_crop)
        cp_layout.addWidget(self.btn_save)
        
        self.btn_discard = QPushButton("❌ DISCARD (Esc)")
        self.btn_discard.setFixedHeight(40)
        self.btn_discard.clicked.connect(self.discard_crop)
        cp_layout.addWidget(self.btn_discard)
        
        self.confirm_panel.hide()
        splitter.addWidget(self.confirm_panel)
        
        layout.addWidget(splitter)
        
        # Shortcut setup
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        if self.confirm_panel.isVisible():
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                self.save_crop()
            elif event.key() == Qt.Key.Key_Escape:
                self.discard_crop()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z:
            self.discard_crop()
        super().keyPressEvent(event)

    def _set_pdf_batch(self, file_paths):
        """Store unique, existing PDF paths for the current import session."""
        unique = []
        seen = set()
        for path in file_paths or []:
            if not path or path in seen:
                continue
            if not os.path.exists(path):
                continue
            seen.add(path)
            unique.append(path)
        self.pdf_files = unique
        self.current_pdf_index = 0 if unique else -1

    def _status_prefix(self):
        if len(self.pdf_files) <= 1 or self.current_pdf_index < 0:
            return ""
        return f"[PDF {self.current_pdf_index + 1}/{len(self.pdf_files)}] "

    def _has_previous_target(self):
        return self.current_page > 0 or self.current_pdf_index > 0

    def _has_next_target(self):
        return self.current_page < self.total_pages - 1 or (
            0 <= self.current_pdf_index < len(self.pdf_files) - 1
        )

    def _open_adjacent_pdf(self, direction):
        """Move to previous/next PDF when user reaches page boundaries."""
        if not self.pdf_files:
            return False

        target_index = self.current_pdf_index + direction
        if target_index < 0 or target_index >= len(self.pdf_files):
            return False

        target_pdf = self.pdf_files[target_index]
        target_page = 0
        if direction < 0:
            target_total = PDFToImageConverter.get_page_count(target_pdf)
            target_page = max(0, target_total - 1)

        self.open_pdf_at_page(target_pdf, target_page)
        return True

    def _apply_default_page_view(self):
        """Ensure the loaded PDF page becomes visible immediately at the default zoom."""
        if not self.pix_item:
            return

        self.view.set_zoom(self.default_open_zoom)
        self.view.centerOn(self.pix_item.sceneBoundingRect().center())
        self.view.viewport().update()
        self.view.update()

    def start_processing(self, file_paths, auto_crop=False, page_limit=None):
        """Called from MainWindow when files are selected."""
        if not file_paths:
            return

        valid_files = []
        for path in file_paths:
            if not path or not os.path.exists(path):
                continue
            total = PDFToImageConverter.get_page_count(path)
            if total > 0:
                valid_files.append((path, total))

        if not valid_files:
            QMessageBox.critical(
                self,
                "Open PDF Failed",
                "Could not read the selected PDF file(s). Please check and try again.",
            )
            return

        batch_files = [path for path, _total in valid_files]
        self._set_pdf_batch(batch_files)

        first_pdf, first_total = valid_files[0]

        last_page = None
        if page_limit is not None:
            try:
                last_page = max(1, int(page_limit))
            except Exception:
                last_page = None

        batch_ran = False
        if auto_crop:
            if not self._ensure_yolo_detector():
                QMessageBox.warning(
                    self,
                    "AI Not Available",
                    "YOLO model is not available. Switched to manual cropping mode."
                )
            else:
                batch_ran = True
                if last_page is None:
                    last_page = first_total
                summary = self.auto_crop_files_up_to_page(batch_files, last_page)
                if summary["saved"] > 0:
                    msg = (
                        f"Auto-cropped {summary['saved']} question(s) "
                        f"from {summary['processed_pages']} page(s)."
                    )
                    if summary["failed"] > 0:
                        msg += f"\n{summary['failed']} crop(s) failed."
                    if summary["canceled"]:
                        msg += "\nOperation canceled before completion."
                    QMessageBox.information(self, "Auto Crop Complete", msg)
                else:
                    QMessageBox.warning(
                        self,
                        "Auto Crop",
                        "No questions were saved. You can continue with manual cropping."
                    )

        # Open first PDF and land on the last processed page so user can continue manually.
        landing_page = 0
        if batch_ran and last_page:
            landing_page = max(0, min(first_total - 1, last_page - 1))
        self.open_pdf_at_page(first_pdf, landing_page)

    def open_pdf_at_page(self, pdf_path, page_index=0):
        """Open a specific PDF and move editor to the given page index."""
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "File Missing", "Could not locate the source PDF.")
            return

        if pdf_path in self.pdf_files:
            self.current_pdf_index = self.pdf_files.index(pdf_path)
        else:
            # Opening an external PDF should not keep stale batch navigation.
            self.pdf_files = [pdf_path]
            self.current_pdf_index = 0

        self.current_pdf = pdf_path
        self.total_pages = PDFToImageConverter.get_page_count(self.current_pdf)
        if self.total_pages <= 0:
            QMessageBox.critical(self, "Open PDF Failed", "Could not read this PDF. Please check the file and try again.")
            return

        self.current_page = max(0, min(int(page_index), self.total_pages - 1))
        self.load_current_page()

    def _collect_valid_detections(self, detections, width, height):
        """Filter and clamp detection boxes to image boundaries."""
        valid = []
        for det in detections:
            normalized = self._normalize_bbox(det.get("bbox", (0, 0, 0, 0)), width, height)
            if not normalized:
                continue

            x1, y1, x2, y2 = normalized
            valid.append(
                {
                    "bbox": (x1, y1, x2, y2),
                    "confidence": float(det.get("confidence", 0.0)),
                    "label": det.get("label", "question"),
                }
            )
        return valid

    def _save_detections_from_pil(self, pil_img, detections, pdf_path, page_num):
        """Persist crops using PIL image and validated detections."""
        saved = 0
        failed = 0
        topic = self.edit_topic.text().strip() or "AI Auto Crop"
        marks = self.edit_marks.value()
        pdf_name = os.path.basename(pdf_path)
        source_path = os.path.abspath(pdf_path)

        for det in detections:
            try:
                x1, y1, x2, y2 = det["bbox"]
                crop = pil_img.crop((x1, y1, x2, y2))
                metadata = {
                    "marks": marks,
                    "topic": topic,
                    "source_pdf": pdf_name,
                    "source_pdf_path": source_path,
                    "page": int(page_num),
                    "detected_by": "yolov8",
                    "detection_confidence": round(float(det.get("confidence", 0.0)), 4),
                    "detection_label": det.get("label", "question"),
                }
                save_result = self.pm.save_question(pdf_name, metadata, crop)
                success = bool(save_result[0]) if isinstance(save_result, tuple) else bool(save_result)
                if success:
                    saved += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return saved, failed

    def auto_crop_files_up_to_page(self, file_paths, page_limit):
        """Run YOLO auto-crop on all files up to selected page (1-based inclusive)."""
        page_limit = max(1, int(page_limit))
        total_pages = 0
        page_counts = {}
        for path in file_paths:
            count = max(0, PDFToImageConverter.get_page_count(path))
            page_counts[path] = count
            total_pages += min(count, page_limit)

        progress = QProgressDialog("Auto-cropping questions...", "Cancel", 0, max(1, total_pages), self)
        progress.setWindowTitle("AI Auto Crop")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        processed = 0
        saved_total = 0
        failed_total = 0
        canceled = False

        for path in file_paths:
            if progress.wasCanceled():
                canceled = True
                break

            count = page_counts.get(path, 0)
            if count <= 0:
                continue

            max_pages = min(count, page_limit)
            for page_idx in range(max_pages):
                if progress.wasCanceled():
                    canceled = True
                    break

                progress.setLabelText(f"{os.path.basename(path)} - Page {page_idx + 1}/{max_pages}")
                QApplication.processEvents()

                pil_img = PDFToImageConverter.convert_page(path, page_idx, dpi=300)
                if not pil_img:
                    failed_total += 1
                    processed += 1
                    progress.setValue(processed)
                    continue

                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")

                detections = self.yolo_detector.detect_questions(pil_img)
                valid_detections = self._collect_valid_detections(detections, pil_img.width, pil_img.height)
                saved, failed = self._save_detections_from_pil(pil_img, valid_detections, path, page_idx + 1)
                saved_total += saved
                failed_total += failed + max(0, len(detections) - len(valid_detections))

                processed += 1
                progress.setValue(processed)

            if canceled:
                break

        progress.close()
        return {
            "processed_pages": processed,
            "saved": saved_total,
            "failed": failed_total,
            "canceled": canceled,
        }

    def load_current_page(self):
        if not self.current_pdf: return
        self.lbl_info.setText(
            f"{self._status_prefix()}Loading '{os.path.basename(self.current_pdf)}' Page {self.current_page+1}..."
        )
        
        # Reset scene state
        self.scene.clear()
        self.pix_item = None
        self._img_data = None
        self.view._current_rect = None
        self.view._is_drawing = False

        # High-res conversion with cache
        try:
            cache_key = (self.current_pdf, self.current_page)
            if cache_key in self.page_cache:
                pix = self.page_cache[cache_key]
            else:
                pil_img = PDFToImageConverter.convert_page(self.current_pdf, self.current_page, dpi=300)
                if not pil_img:
                    self.lbl_info.setText("Failed to load page. Check if PDF is valid.")
                    QMessageBox.warning(self, "Load Error", f"Could not render page {self.current_page+1}")
                    return
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                self._img_data = data  # Keep buffer alive
                w, h = pil_img.size
                bytes_per_line = w * 3
                qimg = QImage(self._img_data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimg.copy())
                self.page_cache[cache_key] = pix
                # simple LRU trim
                if len(self.page_cache) > self.cache_limit:
                    self.page_cache.pop(next(iter(self.page_cache)))
            self.pix_item = QGraphicsPixmapItem(pix)
            self.scene.addItem(self.pix_item)
            self.view.setSceneRect(self.scene.itemsBoundingRect())
            
            # Apply fixed default zoom after layout is ready so the page shows immediately.
            self._apply_default_page_view()
            QTimer.singleShot(0, self._apply_default_page_view)
            
            self.lbl_info.setText(
                f"{self._status_prefix()}{os.path.basename(self.current_pdf)} | "
                f"Page {self.current_page+1} of {self.total_pages}"
            )
            self.btn_prev.setEnabled(self._has_previous_target())
            self.btn_next.setEnabled(self._has_next_target())
            self.confirm_panel.hide()
            self.save_editor_state()
        except Exception as e:
            self.lbl_info.setText("Failed to load page.")
            QMessageBox.critical(self, "Load Error", f"Error loading page {self.current_page+1}:\n{e}")

    def save_editor_state(self):
        try:
            os.makedirs("config", exist_ok=True)
            data = {
                "pdf_path": self.current_pdf,
                "page": self.current_page
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def on_crop_defined(self, rect):
        """User finished drawing a crop square."""
        if not self.pix_item: 
            return
            
        # 1. Capture the crop from the high-res pixmap
        full_pix = self.pix_item.pixmap()
        crop = full_pix.copy(rect.toRect())
        
        # 2. Show Preview
        self.preview_img.setPixmap(crop.scaled(self.preview_img.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.current_crop_pix = crop
        self.confirm_panel.show()
        self.setFocus()

    def save_crop(self):
        if not hasattr(self, 'current_crop_pix'): return

        pil_img = self._qimage_to_pil(self.current_crop_pix.toImage())
        
        data = {
            "marks": self.edit_marks.value(),
            "topic": self.edit_topic.text(),
            "source_pdf": os.path.basename(self.current_pdf),
            "source_pdf_path": os.path.abspath(self.current_pdf) if self.current_pdf else "",
            "page": self.current_page + 1
        }
        
        save_result = self.pm.save_question(os.path.basename(self.current_pdf), data, pil_img)
        if isinstance(save_result, tuple):
            success, q_id = save_result
        else:
            success, q_id = bool(save_result), None

        if success:
            if q_id:
                self.lbl_info.setText(f"Successfully saved {q_id}!")
            else:
                self.lbl_info.setText("Successfully saved crop!")
            self.discard_crop() # Hide panel and clear rect
        else:
            QMessageBox.critical(self, "Error", "Failed to save question.")

    def _qimage_to_pil(self, qimg):
        """Convert QImage to PIL Image in RGB mode."""
        from PIL import Image

        img_rgba = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
        byte_array = img_rgba.bits().tobytes()
        pil_img = Image.frombuffer(
            "RGBA",
            (img_rgba.width(), img_rgba.height()),
            byte_array,
            "raw",
            "RGBA",
            img_rgba.bytesPerLine(),
            1,
        ).copy()
        return pil_img.convert("RGB")

    def _normalize_bbox(self, bbox, max_w, max_h):
        """Clamp bbox to image bounds and return valid integer coordinates."""
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        x1 = max(0, min(max_w, x1))
        x2 = max(0, min(max_w, x2))
        y1 = max(0, min(max_h, y1))
        y2 = max(0, min(max_h, y2))

        if x2 - x1 < 5 or y2 - y1 < 5:
            return None
        return x1, y1, x2, y2

    def _auto_crop_and_save_detections(self, detections):
        """Save all detections as cropped question images."""
        if not self.pix_item or not self.current_pdf:
            return 0, len(detections)

        full_pix = self.pix_item.pixmap()
        img_w = full_pix.width()
        img_h = full_pix.height()

        saved = 0
        failed = 0
        topic = self.edit_topic.text().strip() or "AI Auto Crop"
        marks = self.edit_marks.value()
        pdf_name = os.path.basename(self.current_pdf)

        for det in detections:
            normalized = self._normalize_bbox(det.get("bbox", (0, 0, 0, 0)), img_w, img_h)
            if not normalized:
                failed += 1
                continue

            x1, y1, x2, y2 = normalized
            crop_pix = full_pix.copy(QRect(x1, y1, x2 - x1, y2 - y1))
            pil_img = self._qimage_to_pil(crop_pix.toImage())

            metadata = {
                "marks": marks,
                "topic": topic,
                "source_pdf": pdf_name,
                "source_pdf_path": os.path.abspath(self.current_pdf) if self.current_pdf else "",
                "page": self.current_page + 1,
                "detected_by": "yolov8",
                "detection_confidence": round(float(det.get("confidence", 0.0)), 4),
                "detection_label": det.get("label", "question"),
            }

            save_result = self.pm.save_question(pdf_name, metadata, pil_img)
            success = bool(save_result[0]) if isinstance(save_result, tuple) else bool(save_result)
            if success:
                saved += 1
            else:
                failed += 1

        return saved, failed

    def discard_crop(self):
        self.confirm_panel.hide()
        if hasattr(self.view, '_current_rect') and self.view._current_rect:
            try:
                if self.view._current_rect.scene() is not None:
                    self.scene.removeItem(self.view._current_rect)
            except RuntimeError:
                pass
            self.view._current_rect = None
        self.setFocus()

    def on_show(self):
        if self.current_pdf:
            return
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pdf_path = data.get("pdf_path")
            page = int(data.get("page", 0))
            if pdf_path and os.path.exists(pdf_path):
                res = QMessageBox.question(
                    self,
                    "Resume Last PDF",
                    f"Resume editing:\n{os.path.basename(pdf_path)} (Page {page+1})?"
                )
                if res == QMessageBox.StandardButton.Yes:
                    self.open_pdf_at_page(pdf_path, page)
        except Exception:
            pass

    def show_full_preview(self):
        if not hasattr(self, 'current_crop_pix'):
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Cropped Preview")
        dlg.resize(900, 700)
        layout = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setPixmap(self.current_crop_pix.scaled(860, 640, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(lbl)
        dlg.exec()

    def on_zoom_changed(self, zoom):
        pct = int(zoom * 100)
        self.zoom_label.setText(f"{pct}%")
        if self.zoom_slider.value() != pct:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(pct)
            self.zoom_slider.blockSignals(False)

    def on_zoom_slider(self, value):
        self.view.set_zoom(value / 100.0)

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.load_current_page()
            return
        self._open_adjacent_pdf(1)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_current_page()
            return
        self._open_adjacent_pdf(-1)

    def run_ai_detection(self):
        '''Run YOLO AI detection on current page'''
        if not self.pix_item:
            QMessageBox.warning(self, "No Page", "Please open a PDF first.")
            return
        
        if not self._ensure_yolo_detector():
            QMessageBox.warning(
                self, "AI Not Available", 
                "YOLO model not loaded. Please check ai_detection settings in config.json."
            )
            return
        
        self.lbl_info.setText("Running AI detection...")
        self.btn_ai_detect.setEnabled(False)
        
        try:
            # Clear previous AI detections
            self.clear_ai_crops()
            
            # Get current page image from pixmap
            full_pix = self.pix_item.pixmap()
            qimg = full_pix.toImage()
            pil_img = self._qimage_to_pil(qimg)
            
            # Run detection
            detections = self.yolo_detector.detect_questions(pil_img)
            
            if not detections:
                self.lbl_info.setText("No questions detected on this page.")
                self.btn_ai_detect.setEnabled(True)
                return

            valid_detections = self._collect_valid_detections(
                detections, full_pix.width(), full_pix.height()
            )

            if not valid_detections:
                self.lbl_info.setText("No valid question boxes detected on this page.")
                return

            for det in valid_detections:
                x1, y1, x2, y2 = det["bbox"]
                crop_rect = ManualCropRect(x1, y1, x2 - x1, y2 - y1)
                self.scene.addItem(crop_rect)
                self.ai_crop_rects.append(crop_rect)

            saved_count, failed_count = self._auto_crop_and_save_detections(valid_detections)
            self.clear_ai_crops()

            if saved_count == 0:
                self.lbl_info.setText("AI detection ran, but no questions were saved.")
                QMessageBox.warning(self, "Auto Crop", "Detection completed, but no questions were saved.")
                return

            self.lbl_info.setText(f"AI auto-cropped and saved {saved_count} question(s).")
            if failed_count:
                QMessageBox.warning(
                    self,
                    "Partial Save",
                    f"Saved {saved_count} question(s), but {failed_count} detection(s) failed.",
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Detection Error", f"Error during AI detection: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.btn_ai_detect.setEnabled(True)
    
    def clear_ai_crops(self):
        '''Remove all AI-generated crop rectangles'''
        for rect in self.ai_crop_rects:
            if rect.scene():
                self.scene.removeItem(rect)
        self.ai_crop_rects = []
