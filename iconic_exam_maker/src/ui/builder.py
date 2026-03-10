import os
import json
import tempfile
import shutil
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
                               QPushButton, QListWidget, QListWidgetItem, QFrame,
                               QFileDialog, QMessageBox, QSpinBox, QLineEdit, QDialog,
                               QComboBox, QDoubleSpinBox, QInputDialog)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer, QModelIndex
from PySide6.QtGui import QPixmap, QImage, QShortcut, QKeySequence
from PIL import Image
from src.utils.exporter import PDFExporter
from src.utils.converter import PDFToImageConverter


class InlineCropAdjustDialog(QDialog):
    """Quick crop/rotate editor for question images directly from Builder."""

    def __init__(self, img_path, parent=None):
        super().__init__(parent)
        self.img_path = img_path
        self._preview_data = None

        self.setWindowTitle("Inline Crop Adjust")
        self.resize(920, 560)

        self._load_source_image()
        self._build_ui()
        self._update_preview()

    def _load_source_image(self):
        if not self.img_path or not os.path.exists(self.img_path):
            raise FileNotFoundError("Question image not found.")
        self._orig_img = Image.open(self.img_path).convert("RGB")

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        self.preview = QLabel("Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(620, 500)
        self.preview.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #D6D6D6; border-radius: 4px;"
        )
        root.addWidget(self.preview, 1)

        side = QVBoxLayout()
        side.setSpacing(10)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #475569; font-size: 12px;")
        side.addWidget(self.lbl_info)

        self.rotate_combo = QComboBox()
        self.rotate_combo.addItems(["Rotate: 0°", "Rotate: 90°", "Rotate: 180°", "Rotate: 270°"])
        side.addWidget(self.rotate_combo)

        max_x = max(0, self._orig_img.width // 3)
        max_y = max(0, self._orig_img.height // 3)

        self.spin_left = QSpinBox()
        self.spin_left.setRange(0, max_x)
        self.spin_left.setPrefix("Left: ")
        side.addWidget(self.spin_left)

        self.spin_right = QSpinBox()
        self.spin_right.setRange(0, max_x)
        self.spin_right.setPrefix("Right: ")
        side.addWidget(self.spin_right)

        self.spin_top = QSpinBox()
        self.spin_top.setRange(0, max_y)
        self.spin_top.setPrefix("Top: ")
        side.addWidget(self.spin_top)

        self.spin_bottom = QSpinBox()
        self.spin_bottom.setRange(0, max_y)
        self.spin_bottom.setPrefix("Bottom: ")
        side.addWidget(self.spin_bottom)

        hint = QLabel("Tip: Use small trim values for clean edges.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748B; font-size: 11px;")
        side.addWidget(hint)
        side.addStretch()

        actions = QHBoxLayout()
        btn_reset = QPushButton("Reset")
        btn_cancel = QPushButton("Cancel")
        btn_save = QPushButton("Save")
        btn_save.setObjectName("success")
        actions.addWidget(btn_reset)
        actions.addWidget(btn_cancel)
        actions.addWidget(btn_save)
        side.addLayout(actions)

        root.addLayout(side)

        for control in (
            self.rotate_combo,
            self.spin_left,
            self.spin_right,
            self.spin_top,
            self.spin_bottom,
        ):
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(self._update_preview)
            else:
                control.currentIndexChanged.connect(self._update_preview)
        self.rotate_combo.currentIndexChanged.connect(self._update_preview)

        btn_reset.clicked.connect(self._reset_controls)
        btn_cancel.clicked.connect(self.reject)
        btn_save.clicked.connect(self._save_changes)

    def _reset_controls(self):
        self.rotate_combo.setCurrentIndex(0)
        self.spin_left.setValue(0)
        self.spin_right.setValue(0)
        self.spin_top.setValue(0)
        self.spin_bottom.setValue(0)
        self._update_preview()

    def _build_result_image(self):
        img = self._orig_img.copy()

        rotate_map = {0: 0, 1: 90, 2: 180, 3: 270}
        degrees = rotate_map.get(self.rotate_combo.currentIndex(), 0)
        if degrees:
            # Pillow rotates counter-clockwise for positive angle.
            img = img.rotate(-degrees, expand=True)

        left = int(self.spin_left.value())
        right = int(self.spin_right.value())
        top = int(self.spin_top.value())
        bottom = int(self.spin_bottom.value())

        left = max(0, min(left, img.width - 2))
        right = max(0, min(right, img.width - left - 2))
        top = max(0, min(top, img.height - 2))
        bottom = max(0, min(bottom, img.height - top - 2))

        x1 = left
        y1 = top
        x2 = max(x1 + 2, img.width - right)
        y2 = max(y1 + 2, img.height - bottom)

        x2 = min(x2, img.width)
        y2 = min(y2, img.height)
        return img.crop((x1, y1, x2, y2))

    def _update_preview(self, *_args):
        try:
            img = self._build_result_image()
            self.lbl_info.setText(f"Preview size: {img.width} x {img.height}")
            data = img.tobytes("raw", "RGB")
            self._preview_data = data
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.preview.setPixmap(
                pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        except Exception as e:
            self.lbl_info.setText(f"Preview error: {e}")

    def _save_changes(self):
        try:
            img = self._build_result_image()
            img.save(self.img_path)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not save edited crop:\n{e}")


class ExamBuilder(QWidget):
    def __init__(self, project_manager):
        super().__init__()
        self.pm = project_manager
        self.selected_questions = []
        self.export_history = []
        self.state_path = os.path.join("config", "builder_state.json")
        self.preset_path = os.path.join("config", "builder_presets.json")
        self.snapshot_dir = os.path.join("config", "builder_snapshots")
        self._preview_cache = {"hash": None, "path": None}
        self._history_suspended = False
        self._undo_stack = []
        self._redo_stack = []
        self._history_limit = 80
        self._suspend_row_move_snapshot = False
        self._live_preview_cache_hash = None
        self._live_preview_pdf = os.path.join(tempfile.gettempdir(), "iconic_exam_live_preview.pdf")
        self._live_preview_page = 0
        self._live_preview_total = 0
        self.design_presets = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─────────────────────────────────────────────────────────────────────
        # TOP TOOLBAR  (Acrobat-style header bar with grouped export actions)
        # ─────────────────────────────────────────────────────────────────────
        toolbar_bar = QWidget()
        toolbar_bar.setObjectName("toolbar")
        toolbar_bar.setStyleSheet(
            "QWidget#toolbar { background-color: #FFFFFF; border-bottom: 1px solid #E0E0E0; }"
        )
        toolbar_bar.setFixedHeight(72)
        tb_layout = QHBoxLayout(toolbar_bar)
        tb_layout.setContentsMargins(16, 8, 16, 8)
        tb_layout.setSpacing(6)

        # Page Title
        lbl_page = QLabel("Paper Builder")
        lbl_page.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #333333; padding-right: 16px;"
        )
        tb_layout.addWidget(lbl_page)

        # Thin separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #D6D6D6;")
        tb_layout.addWidget(sep1)

        # PRIMARY: Export PDF (the most-used action)
        self.btn_export = QPushButton("↓  Export\nPDF")
        self.btn_export.setObjectName("success")
        self.btn_export.setFixedHeight(48)
        self.btn_export.setMinimumWidth(100)
        self.btn_export.setToolTip("Export the full exam paper as PDF  [Ctrl+S]")
        self.btn_export.setStyleSheet(
            "QPushButton { background-color: #1473E6; color: #FFF; border: none;"
            " border-radius: 6px; font-weight: 700; font-size: 13px; padding: 4px; }"
            "QPushButton:hover { background-color: #0D66D0; }"
            "QPushButton:pressed { background-color: #0054B6; }"
        )
        self.btn_export.clicked.connect(self.handle_export)
        tb_layout.addWidget(self.btn_export)

        # SECONDARY group: Preview / Test / DOCX / Answer Key
        for label, tip, slot in [
            ("Preview\nHeader", "Preview the header layout only", self.handle_preview_header),
            ("Test\nExport",    "Quick PDF with header only",     self.handle_test_export),
            ("Export\nDOCX",   "Export as Word document",         self.handle_export_docx),
            ("Answer\nKey",    "Export the answer key as PDF",    self.handle_export_key),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(48)
            btn.setMinimumWidth(80)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            btn.setStyleSheet(
                "QPushButton { background-color: #F8F9FA; color: #333; border: none;"
                " border-radius: 6px; font-weight: 600; font-size: 12px; padding: 4px; }"
                "QPushButton:hover { background-color: #E9ECEF; }"
            )
            tb_layout.addWidget(btn)
            if label == "Preview\nHeader":
                self.btn_preview = btn
            elif label == "Test\nExport":
                self.btn_test_export = btn
            elif label == "Export\nDOCX":
                self.btn_export_docx = btn
            elif label == "Answer\nKey":
                self.btn_export_key = btn

        tb_layout.addStretch()

        # Undo / Redo (right-aligned in toolbar)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #D6D6D6;")
        tb_layout.addWidget(sep2)

        for label, tip, slot_name in [
            ("↩ Undo", "Undo  Ctrl+Z", "undo_change"),
            ("↪ Redo", "Redo  Ctrl+Y", "redo_change"),
        ]:
            b = QPushButton(label)
            b.setFixedSize(76, 36)
            b.setToolTip(tip)
            b.clicked.connect(getattr(self, slot_name))
            b.setStyleSheet(
                "QPushButton { background-color: #F4F4F4; color: #555; border: 1px solid #D0D0D0;"
                " border-radius: 4px; font-weight: 600; font-size: 12px; }"
                "QPushButton:hover { background-color: #EAEAEA; }"
                "QPushButton:disabled { color: #BBBBBB; }"
            )
            tb_layout.addWidget(b)
            if slot_name == "undo_change":
                self.btn_undo = b
            else:
                self.btn_redo = b

        layout.addWidget(toolbar_bar)

        # ─────────────────────────────────────────────────────────────────────
        # CONTROLS BAR  (single collapsible strip: search | design | presets | snapshots)
        # ─────────────────────────────────────────────────────────────────────
        ctrl_bar = QWidget()
        ctrl_bar.setStyleSheet("background-color: #F4F4F4; border-bottom: 1px solid #D6D6D6;")
        ctrl_bar.setFixedHeight(48)
        cb_layout = QHBoxLayout(ctrl_bar)
        cb_layout.setContentsMargins(12, 6, 12, 6)
        cb_layout.setSpacing(8)

        # Search / filter (restored)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍  Filter…")
        self.filter_input.setFixedWidth(160)
        self.filter_input.setFixedHeight(30)
        self.filter_input.textChanged.connect(self.apply_filter)
        cb_layout.addWidget(self.filter_input)

        ctrl_sep1 = QFrame(); ctrl_sep1.setFrameShape(QFrame.Shape.VLine)
        ctrl_sep1.setStyleSheet("color: #C4C4C4;")
        cb_layout.addWidget(ctrl_sep1)

        # Design controls group
        for lbl_txt, widget_factory in [
            ("Q# Style", None),
            ("Start №",  None),
            ("Gap (mm)", None),
            ("View",     None),
        ]:
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
            cb_layout.addWidget(lbl)

        # (We'll replace above with actual widgets — clear and redo)
        # Remove the placeholder labels we just added: easier to rebuild
        for i in range(8):
            item = cb_layout.takeAt(cb_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()

        # Q# Style
        lbl_ns = QLabel("Q# Style:")
        lbl_ns.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
        cb_layout.addWidget(lbl_ns)
        self.cmb_qnum_style = QComboBox()
        self.cmb_qnum_style.addItems(["01.", "1.", "Q1."])
        self.cmb_qnum_style.setCurrentText("01.")
        self.cmb_qnum_style.setToolTip("Question number style in exported paper")
        self.cmb_qnum_style.setFixedHeight(32)
        self.cmb_qnum_style.setFixedWidth(72)
        cb_layout.addWidget(self.cmb_qnum_style)

        # Start №
        lbl_sn = QLabel("Start №:")
        lbl_sn.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
        cb_layout.addWidget(lbl_sn)
        self.spin_start_number = QSpinBox()
        self.spin_start_number.setRange(1, 999)
        self.spin_start_number.setValue(1)
        self.spin_start_number.setFixedHeight(32)
        self.spin_start_number.setFixedWidth(64)
        cb_layout.addWidget(self.spin_start_number)

        # Gap
        lbl_gap = QLabel("Gap mm:")
        lbl_gap.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
        cb_layout.addWidget(lbl_gap)
        self.spin_gap_mm = QDoubleSpinBox()
        self.spin_gap_mm.setRange(2.0, 20.0)
        self.spin_gap_mm.setSingleStep(0.5)
        self.spin_gap_mm.setValue(8.0)
        self.spin_gap_mm.setFixedHeight(32)
        self.spin_gap_mm.setFixedWidth(72)
        self.spin_gap_mm.setToolTip("Vertical space between questions")
        cb_layout.addWidget(self.spin_gap_mm)

        # View size
        lbl_vs = QLabel("View:")
        lbl_vs.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
        cb_layout.addWidget(lbl_vs)
        self.view_size_combo = QComboBox()
        self.view_size_combo.addItems(["Compact", "Comfort", "Large"])
        self.view_size_combo.setCurrentText("Compact")
        self.view_size_combo.currentTextChanged.connect(self.apply_view_size)
        self.view_size_combo.setFixedHeight(32)
        self.view_size_combo.setFixedWidth(86)
        cb_layout.addWidget(self.view_size_combo)

        ctrl_sep2 = QFrame(); ctrl_sep2.setFrameShape(QFrame.Shape.VLine)
        ctrl_sep2.setStyleSheet("color: #C4C4C4;")
        cb_layout.addWidget(ctrl_sep2)

        # Reverse order checkbox
        self.chk_reverse_order = QCheckBox("Reverse Order")
        self.chk_reverse_order.setToolTip("Export questions from bottom to top.")
        self.chk_reverse_order.setChecked(True)
        self.chk_reverse_order.setStyleSheet("font-size: 11px; color: #555;")
        self.chk_reverse_order.toggled.connect(self.on_design_setting_changed)
        cb_layout.addWidget(self.chk_reverse_order)

        ctrl_sep3 = QFrame(); ctrl_sep3.setFrameShape(QFrame.Shape.VLine)
        ctrl_sep3.setStyleSheet("color: #C4C4C4;")
        cb_layout.addWidget(ctrl_sep3)

        # Preset combo + actions
        lbl_pre = QLabel("Preset:")
        lbl_pre.setStyleSheet("font-size: 11px; color: #555; font-weight: 600;")
        cb_layout.addWidget(lbl_pre)
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedHeight(32)
        self.preset_combo.setMinimumWidth(130)
        cb_layout.addWidget(self.preset_combo)

        for label, tip, slot_name in [
            ("Apply", "Apply selected preset", "apply_selected_preset"),
            ("Save",  "Save current settings as preset", "save_current_preset"),
            ("Del",   "Delete selected preset", "delete_selected_preset"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.setFixedWidth(46 if label == "Del" else 52)
            b.setToolTip(tip)
            b.clicked.connect(getattr(self, slot_name))
            b.setStyleSheet(
                "QPushButton { background-color: #FFFFFF; color: #333; border: 1px solid #C4C4C4;"
                " border-radius: 3px; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background-color: #F4F4F4; }"
            )
            cb_layout.addWidget(b)
            if slot_name == "apply_selected_preset":
                self.btn_apply_preset = b
            elif slot_name == "save_current_preset":
                self.btn_save_preset = b
            else:
                self.btn_delete_preset = b

        ctrl_sep4 = QFrame(); ctrl_sep4.setFrameShape(QFrame.Shape.VLine)
        ctrl_sep4.setStyleSheet("color: #C4C4C4;")
        cb_layout.addWidget(ctrl_sep4)

        # (Removed Snapshot from this bar to match design)
        cb_layout.addStretch()
        layout.addWidget(ctrl_bar)

        # ─────────────────────────────────────────────────────────────────────
        # SELECTION ACTION BAR  (context-sensitive, shown above the list)
        # ─────────────────────────────────────────────────────────────────────
        sel_bar = QWidget()
        sel_bar.setStyleSheet(
            "background-color: #FAFAFA; border-bottom: 1px solid #EBEBEB;"
        )
        sel_bar.setFixedHeight(44)
        sel_layout = QHBoxLayout(sel_bar)
        sel_layout.setContentsMargins(16, 4, 16, 4)
        sel_layout.setSpacing(6)

        self.lbl_selected = QLabel("No question selected")
        self.lbl_selected.setStyleSheet("font-size: 11px; color: #888; font-weight: 700; letter-spacing: 0.3px;")
        sel_layout.addWidget(self.lbl_selected, 1)

        action_btns = [
            ("👁 PREVIEW",   "preview_selected_item",  "#1473E6", "#DDEEFE"),
            ("RE-EDIT",      "adjust_selected_crop",   "#333333", "#F0F0F0"),
            ("▲ MOVE UP",   None,                      "#333333", "#F0F0F0"),
            ("▼ MOVE DOWN", None,                      "#333333", "#F0F0F0"),
            ("✕ REMOVE",    "remove_selected_item",    "#CC0000", "#FFF2F2"),
        ]
        for label, slot_name, color, bg in action_btns:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setMinimumWidth(74)
            b.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: {color}; border: 1px solid #D6D6D6;"
                " border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px; }"
                f"QPushButton:hover {{ background-color: {color}; color: #FFF; }}"
                "QPushButton:disabled { color: #BBBBBB; background-color: #F8F8F8; border-color: #E8E8E8; }"
            )
            if slot_name:
                b.clicked.connect(getattr(self, slot_name))
            if label == "▲ MOVE UP":
                b.setAutoRepeat(True)
                b.setAutoRepeatDelay(250)
                b.setAutoRepeatInterval(70)
                b.clicked.connect(lambda: self.move_selected_item(-1))
                self.btn_selected_up = b
            elif label == "▼ MOVE DOWN":
                b.setAutoRepeat(True)
                b.setAutoRepeatDelay(250)
                b.setAutoRepeatInterval(70)
                b.clicked.connect(lambda: self.move_selected_item(1))
                self.btn_selected_down = b
            elif label == "👁 PREVIEW":
                self.btn_selected_preview = b
            elif label == "RE-EDIT":
                self.btn_selected_edit = b
            elif label == "✕ REMOVE":
                self.btn_selected_delete = b
            sel_layout.addWidget(b)

        layout.addWidget(sel_bar)

        # ─────────────────────────────────────────────────────────────────────
        # MAIN CONTENT  (question list ← left | live preview → right)
        # ─────────────────────────────────────────────────────────────────────
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet("background-color: #F0F0F0;")
        content_h = QHBoxLayout(content_wrapper)
        content_h.setContentsMargins(12, 12, 12, 12)
        content_h.setSpacing(12)

        # — Question List ——————————————————————————————————————————————————
        list_frame = QFrame()
        list_frame.setObjectName("card")
        list_frame.setStyleSheet(
            "QFrame#card { background-color: #FFFFFF; border: 1px solid #D6D6D6;"
            " border-radius: 4px; }"
        )
        list_v = QVBoxLayout(list_frame)
        list_v.setContentsMargins(0, 0, 0, 0)
        list_v.setSpacing(0)

        self.q_list = QListWidget()
        self.q_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.q_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.q_list.setSpacing(6)
        # 4-column grid-flow mode
        self.q_list.setFlow(QListWidget.Flow.LeftToRight)
        self.q_list.setWrapping(True)
        self.q_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.q_list.setUniformItemSizes(False)
        self.q_list.setStyleSheet(
            "QListWidget { background-color: #F0F0F0; border: none; outline: none; padding: 8px; }"
            "QListWidget::item { border-radius: 6px; }"
            "QListWidget::item:selected { background-color: transparent; }"
        )
        self.q_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.q_list.model().rowsMoved.connect(self.update_stats)
        self.q_list.model().rowsAboutToBeMoved.connect(self._on_rows_about_to_be_moved)
        self.q_list.currentItemChanged.connect(self.on_selected_item_changed)
        self.q_list.itemDoubleClicked.connect(self.preview_item)
        list_v.addWidget(self.q_list)

        content_h.addWidget(list_frame, 3)

        # — Right Panel ————————————————————————————————————————————————————
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # Live Preview card
        self.live_preview_frame = QFrame()
        self.live_preview_frame.setObjectName("card")
        self.live_preview_frame.setStyleSheet(
            "QFrame#card { background-color: #FFFFFF; border: 1px solid #D6D6D6;"
            " border-radius: 4px; }"
        )
        self.live_preview_frame.setMinimumWidth(300)
        self.live_preview_frame.setMaximumWidth(360)
        lp_layout = QVBoxLayout(self.live_preview_frame)
        lp_layout.setContentsMargins(10, 10, 10, 10)
        lp_layout.setSpacing(6)

        lp_top = QHBoxLayout()
        lp_title = QLabel("Live Preview")
        lp_title.setStyleSheet("font-weight: 700; color: #333333; font-size: 12px;")
        lp_top.addWidget(lp_title)
        lp_top.addStretch()
        self.chk_auto_live_preview = QCheckBox("Auto")
        self.chk_auto_live_preview.setChecked(True)
        self.chk_auto_live_preview.setStyleSheet("font-size: 11px; color: #555;")
        lp_top.addWidget(self.chk_auto_live_preview)
        self.btn_live_refresh = QPushButton("⟳")
        self.btn_live_refresh.setFixedSize(28, 28)
        self.btn_live_refresh.setToolTip("Refresh preview")
        self.btn_live_refresh.setStyleSheet(
            "QPushButton { background-color: #F4F4F4; border: 1px solid #D6D6D6;"
            " border-radius: 3px; font-size: 14px; }"
            "QPushButton:hover { background-color: #DDEEFE; color: #1473E6; }"
        )
        self.btn_live_refresh.clicked.connect(lambda: self.refresh_live_preview(force=True))
        lp_top.addWidget(self.btn_live_refresh)
        lp_layout.addLayout(lp_top)

        self.lbl_live_preview = QLabel("Preview will appear here.")
        self.lbl_live_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_live_preview.setMinimumHeight(280)
        self.lbl_live_preview.setStyleSheet(
            "background-color: #F8F8F8; border: 1px solid #D6D6D6; border-radius: 3px;"
            " color: #AAAAAA; font-size: 12px;"
        )
        lp_layout.addWidget(self.lbl_live_preview, 1)

        lp_nav = QHBoxLayout()
        self.btn_live_prev = QPushButton("◀ Prev")
        self.btn_live_prev.setFixedHeight(28)
        self.btn_live_prev.clicked.connect(lambda: self.change_live_preview_page(-1))
        self.lbl_live_page = QLabel("Page 0/0")
        self.lbl_live_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_live_page.setStyleSheet("color: #555; font-weight: 600; font-size: 11px;")
        self.btn_live_next = QPushButton("Next ▶")
        self.btn_live_next.setFixedHeight(28)
        self.btn_live_next.clicked.connect(lambda: self.change_live_preview_page(1))
        for w in (self.btn_live_prev, self.lbl_live_page, self.btn_live_next):
            lp_nav.addWidget(w)
        lp_layout.addLayout(lp_nav)

        right_panel.addWidget(self.live_preview_frame)

        # Open Last Export button (lives naturally in right panel)
        self.btn_open_last = QPushButton("Open Last Export ↗")
        self.btn_open_last.setFixedHeight(34)
        self.btn_open_last.setEnabled(False)
        self.btn_open_last.clicked.connect(self.open_last_export)
        self.btn_open_last.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; color: #555; border: 1px solid #C4C4C4;"
            " border-radius: 3px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #F4F4F4; }"
            "QPushButton:disabled { color: #AAAAAA; }"
        )
        right_panel.addWidget(self.btn_open_last)

        # Keyboard shortcut reference card
        shortcut_card = QFrame()
        shortcut_card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #D6D6D6;"
            " border-radius: 4px; }"
        )
        sc_layout = QVBoxLayout(shortcut_card)
        sc_layout.setContentsMargins(10, 8, 10, 8)
        sc_layout.setSpacing(3)
        sc_title = QLabel("Keyboard Shortcuts")
        sc_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #555; text-transform: uppercase;")
        sc_layout.addWidget(sc_title)
        shortcuts = [
            ("Delete",    "Remove selected"),
            ("Ctrl+↑/↓", "Reorder question"),
            ("Ctrl+D",   "Duplicate"),
            ("Ctrl+N",   "Toggle number"),
            ("Ctrl+E",   "Adjust crop"),
            ("Ctrl+Z/Y", "Undo / Redo"),
        ]
        for key, desc in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(4)
            k = QLabel(key)
            k.setStyleSheet(
                "background-color: #F4F4F4; border: 1px solid #D6D6D6; border-radius: 3px;"
                " font-size: 10px; font-weight: 700; color: #333; padding: 1px 5px;"
            )
            k.setFixedWidth(70)
            d = QLabel(desc)
            d.setStyleSheet("font-size: 10px; color: #717171;")
            row.addWidget(k)
            row.addWidget(d)
            row.addStretch()
            sc_layout.addLayout(row)
        right_panel.addWidget(shortcut_card)
        right_panel.addStretch()

        content_h.addLayout(right_panel, 1)
        layout.addWidget(content_wrapper, 1)

        # ─────────────────────────────────────────────────────────────────────
        # STATUS BAR  (stats + last export info)
        # ─────────────────────────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setStyleSheet(
            "background-color: #FFFFFF; border-top: 1px solid #D6D6D6;"
        )
        status_bar.setFixedHeight(36)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(16, 0, 16, 0)
        sb_layout.setSpacing(16)

        self.lbl_stats = QLabel("Questions: 0 | Marks: 0")
        self.lbl_stats.setStyleSheet("font-weight: 700; color: #333333; font-size: 12px;")
        sb_layout.addWidget(self.lbl_stats)

        sb_layout.addStretch()

        self.lbl_last_export = QLabel("Last export: —")
        self.lbl_last_export.setStyleSheet("color: #717171; font-size: 11px;")
        sb_layout.addWidget(self.lbl_last_export)

        layout.addWidget(status_bar)

        # ─────────────────────────────────────────────────────────────────────
        # Shortcuts & Timers
        # ─────────────────────────────────────────────────────────────────────
        self.delete_shortcut = QShortcut(QKeySequence("Delete"), self.q_list)
        self.delete_shortcut.activated.connect(self.remove_selected_item)
        self.shortcut_move_up = QShortcut(QKeySequence("Ctrl+Up"), self.q_list)
        self.shortcut_move_up.activated.connect(lambda: self.move_selected_item(-1))
        self.shortcut_move_down = QShortcut(QKeySequence("Ctrl+Down"), self.q_list)
        self.shortcut_move_down.activated.connect(lambda: self.move_selected_item(1))
        self.shortcut_duplicate = QShortcut(QKeySequence("Ctrl+D"), self.q_list)
        self.shortcut_duplicate.activated.connect(self.duplicate_selected_item)
        self.shortcut_toggle_number = QShortcut(QKeySequence("Ctrl+N"), self.q_list)
        self.shortcut_toggle_number.activated.connect(self.toggle_selected_number)
        self.shortcut_adjust_crop = QShortcut(QKeySequence("Ctrl+E"), self.q_list)
        self.shortcut_adjust_crop.activated.connect(self.adjust_selected_crop)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_change)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.redo_change)

        self._live_preview_timer = QTimer(self)
        self._live_preview_timer.setInterval(650)
        self._live_preview_timer.setSingleShot(True)
        self._live_preview_timer.timeout.connect(self.refresh_live_preview)
        self._state_save_timer = QTimer(self)
        self._state_save_timer.setInterval(350)
        self._state_save_timer.setSingleShot(True)
        self._state_save_timer.timeout.connect(self._save_builder_state_now)

        # card_w is the fixed card width; thumb height set proportionally.
        # 4-column grid: card width ~160–220px fits 4 cards across a typical ~760px pane
        self._view_profiles = {
            "Compact": {"card_w": 155, "thumb_h": 115,  "margins": (5, 5, 5, 5),
                        "topic_w": 120, "order_w": 34, "marks_w": 0},
            "Comfort": {"card_w": 195, "thumb_h": 145,  "margins": (6, 6, 6, 6),
                        "topic_w": 155, "order_w": 38, "marks_w": 0},
            "Large":   {"card_w": 240, "thumb_h": 185,  "margins": (8, 8, 8, 8),
                        "topic_w": 185, "order_w": 42, "marks_w": 0},
        }
        self._apply_view_profile("Compact")
        self.load_export_history()
        self.load_design_presets()
        self.refresh_snapshot_list()
        self._update_history_buttons()
        self._set_selected_actions_enabled(False)
        self.view_size_combo.currentTextChanged.connect(self.on_design_setting_changed)
        self.spin_start_number.valueChanged.connect(self.on_design_setting_changed)
        self.spin_gap_mm.valueChanged.connect(self.on_design_setting_changed)
        self.cmb_qnum_style.currentTextChanged.connect(self.on_design_setting_changed)


    def add_question(self, q_data, record_history=True, refresh_ui=True):
        """Adds a question to the builder list."""
        if not q_data:
            return

        if record_history:
            self._push_undo_snapshot()

        q_data = dict(q_data)
        q_data.setdefault("id", "Q")
        q_data.setdefault("topic", "")
        q_data.setdefault("marks", 0)
        q_data.setdefault("show_number", True)

        item = QListWidgetItem(self.q_list)
        inner_w = self._card_w - self._card_margins[0] - self._card_margins[2]
        card_h = self._thumb_h + 82   # thumb + badge + topic + strip + spacing
        item.setSizeHint(QSize(self._card_w + 4, card_h + 4))
        item.setData(Qt.ItemDataRole.UserRole, q_data)

        # ── Outer container ───────────────────────────────────────────────────
        container = QFrame()
        container.setObjectName("card")
        container.setFixedWidth(self._card_w)
        container.setStyleSheet(
            "QFrame#card { background-color: #FFFFFF; border: 2px solid #E0E0E0;"
            " border-radius: 8px; }"
            "QFrame#card:hover { border-color: #1473E6; }"
        )
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(*self._card_margins)
        c_layout.setSpacing(4)

        # ── Thumbnail (full inner width, square-ish) ───────────────────────────
        thumb = QLabel()
        thumb.setObjectName("thumb")
        thumb.setFixedSize(inner_w, self._thumb_h)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            "background-color: #F0F0F0; border: none; border-radius: 4px;"
        )
        img_path = q_data.get("img_path")
        if img_path and os.path.exists(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                thumb.setPixmap(pix.scaled(inner_w, self._thumb_h,
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        c_layout.addWidget(thumb)

        # ── Blue pill badge:  No. 01 Q011 ✓  ─────────────────────────────────
        num = self.q_list.count()
        qid = q_data.get('id', 'Q')
        show_num_chk = QCheckBox()
        show_num_chk.setObjectName("show_num_chk")
        show_num_chk.setChecked(bool(q_data.get("show_number", True)))

        pill_row = QHBoxLayout()
        pill_row.setContentsMargins(0, 0, 0, 0)
        pill_row.setSpacing(0)

        number_badge = QPushButton(f"No. {num:02d}  {qid}  ✓")
        number_badge.setObjectName("question_num_badge")
        number_badge.setCheckable(True)
        number_badge.setChecked(bool(q_data.get("show_number", True)))
        number_badge.setFixedHeight(22)
        number_badge.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        number_badge.setStyleSheet(
            "QPushButton { background-color: #1473E6; color: #FFF; border-radius: 11px;"
            "  font-weight: 700; font-size: 10px; padding: 0 8px; border: none; }"
            "QPushButton:checked { background-color: #1473E6; }"
            "QPushButton:hover { background-color: #0D66D0; }"
        )
        # Toggle the show_number flag on click
        number_badge.toggled.connect(
            lambda checked, i=item: (
                (lambda d: (
                    d.update({'show_number': checked}),
                    i.setData(Qt.ItemDataRole.UserRole, d)
                ))(dict(i.data(Qt.ItemDataRole.UserRole) or {}))
            )() or None
        )
        pill_row.addWidget(number_badge, 1)
        c_layout.addLayout(pill_row)

        # ── Topic input ───────────────────────────────────────────────────────
        topic_edit = QLineEdit(q_data.get('topic', ''))
        topic_edit.setPlaceholderText("Topic")
        topic_edit.setObjectName("topic_edit")
        topic_edit.setFixedHeight(22)
        topic_edit.setStyleSheet(
            "QLineEdit { border: 1px solid #D6D6D6; border-radius: 4px;"
            " font-size: 10px; padding: 0 4px; background: #FDFDFD; color: #333; }"
            "QLineEdit:focus { border-color: #1473E6; }"
        )
        c_layout.addWidget(topic_edit)

        # ── Bottom icon strip: [−] [+] [order#] [🗑] ─────────────────────────
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(3)

        btn_style = (
            "QPushButton { background-color: #F4F4F4; color: #555; border: 1px solid #DCDCDC;"
            "  border-radius: 4px; font-size: 13px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { background-color: #E0E0E0; }"
        )
        icon_h = 24

        btn_minus = QPushButton("−")
        btn_minus.setFixedSize(icon_h, icon_h)
        btn_minus.setStyleSheet(btn_style)
        btn_minus.setToolTip("Decrease marks")
        bottom.addWidget(btn_minus)

        btn_plus = QPushButton("+")
        btn_plus.setFixedSize(icon_h, icon_h)
        btn_plus.setStyleSheet(btn_style)
        btn_plus.setToolTip("Increase marks")
        bottom.addWidget(btn_plus)

        order_spin = QSpinBox()
        order_spin.setObjectName("order_spin")
        order_spin.setRange(1, max(1, self.q_list.count()))
        order_spin.setValue(self.q_list.count())
        order_spin.setFixedHeight(icon_h)
        order_spin.setFixedWidth(self._order_w)
        order_spin.setToolTip("Reorder")
        order_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        order_spin.setStyleSheet("font-size: 10px; border: 1px solid #DCDCDC; border-radius: 4px; padding: 0 2px;")
        bottom.addWidget(order_spin)

        bottom.addStretch()

        btn_delete = QPushButton("🗑")
        btn_delete.setFixedSize(icon_h, icon_h)
        btn_delete.setStyleSheet(
            "QPushButton { background-color: #FFF0F0; color: #CC0000; border: 1px solid #FABBBB;"
            "  border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background-color: #CC0000; color: #FFF; }"
        )
        btn_delete.setToolTip("Remove")
        bottom.addWidget(btn_delete)

        c_layout.addLayout(bottom)

        # ── Hidden marks spinbox (data only, no UI) ───────────────────────────
        marks_spin = QSpinBox()
        marks_spin.setRange(0, 100)
        marks_spin.setValue(int(q_data.get('marks', 0)))
        marks_spin.setObjectName("marks_spin")
        marks_spin.hide()

        def on_topic_changed():
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            old_topic = str(data.get("topic", ""))
            new_topic = topic_edit.text().strip()
            if old_topic == new_topic:
                return
            self._push_undo_snapshot()
            data["topic"] = new_topic
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.update_stats()

        def on_marks_changed():
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            old_marks = int(data.get("marks", 0) or 0)
            new_marks = int(marks_spin.value())
            if old_marks == new_marks:
                return
            self._push_undo_snapshot()
            data["marks"] = new_marks
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.update_stats()

        def on_order_changed(value):
            if self.q_list.count() == 0:
                return
            target_row = max(0, min(self.q_list.count() - 1, int(value) - 1))
            self.move_item_to(item, target_row, record_history=True)

        def on_show_number_changed(checked):
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            old = bool(data.get("show_number", True))
            new_val = bool(checked)
            if old == new_val:
                return
            self._push_undo_snapshot()
            data["show_number"] = new_val
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.update_stats()

        def _adjust_marks(delta):
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            cur = int(data.get("marks", 0) or 0)
            new_val = max(0, min(100, cur + delta))
            if cur == new_val:
                return
            self._push_undo_snapshot()
            data["marks"] = new_val
            marks_spin.setValue(new_val)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.update_stats()

        topic_edit.editingFinished.connect(on_topic_changed)
        marks_spin.valueChanged.connect(on_marks_changed)
        order_spin.valueChanged.connect(on_order_changed)
        btn_minus.clicked.connect(lambda: _adjust_marks(-1))
        btn_plus.clicked.connect(lambda: _adjust_marks(1))
        btn_delete.clicked.connect(lambda: self.remove_item(item, confirm=True))

        self.q_list.setItemWidget(item, container)
        self.q_list.setCurrentItem(item)
        if refresh_ui:
            self.update_stats()

    def remove_item(self, item, confirm=False):
        try:
            row = self.q_list.row(item)
        except RuntimeError:
            return
        if row < 0:
            return

        if confirm:
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            qid = str(data.get("id", "this question"))
            reply = QMessageBox.question(
                self,
                "Remove Question",
                f"Remove {qid} from the exam paper builder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._push_undo_snapshot()
        self.q_list.takeItem(row)
        self.update_stats()

    def remove_selected_item(self):
        item = self.q_list.currentItem()
        if item is None:
            return
        self.remove_item(item, confirm=True)

    def _on_rows_about_to_be_moved(self, *_args):
        if self._history_suspended or self._suspend_row_move_snapshot:
            return
        self._push_undo_snapshot()

    def move_item(self, item, direction):
        try:
            row = self.q_list.row(item)
        except RuntimeError:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.q_list.count():
            return
        self.move_item_to(item, new_row, record_history=True)

    def move_item_to(self, item, new_row, record_history=False):
        try:
            row = self.q_list.row(item)
        except RuntimeError:
            return
        if row < 0:
            return
        self.move_row_to(row, new_row, record_history=record_history)

    def move_row_to(self, row, new_row, record_history=False):
        count = self.q_list.count()
        if count <= 1:
            return
        row = int(row)
        new_row = max(0, min(count - 1, int(new_row)))
        if row < 0 or row >= count or row == new_row:
            return
        if record_history:
            self._push_undo_snapshot()
        model = self.q_list.model()
        destination_row = new_row if new_row < row else new_row + 1
        moved_fast = False
        try:
            self._suspend_row_move_snapshot = True
            moved_fast = bool(model.moveRow(QModelIndex(), row, QModelIndex(), destination_row))
        except Exception:
            moved_fast = False
        finally:
            self._suspend_row_move_snapshot = False

        if moved_fast:
            self.q_list.setCurrentRow(new_row)
            self.update_stats()
            return

        # Fallback: rebuild from data if model move is unavailable.
        questions = self.get_questions_in_order()
        moved = questions.pop(row)
        questions.insert(new_row, moved)

        self._history_suspended = True
        try:
            self.q_list.clear()
            for q in questions:
                self.add_question(q, record_history=False, refresh_ui=False)
            if 0 <= new_row < self.q_list.count():
                self.q_list.setCurrentRow(new_row)
        finally:
            self._history_suspended = False

        self.update_stats()

    def move_selected_item(self, direction):
        item = self.q_list.currentItem()
        if not item:
            return
        self.move_item(item, direction)

    def duplicate_selected_item(self):
        item = self.q_list.currentItem()
        if not item:
            return
        data = dict(item.data(Qt.ItemDataRole.UserRole) or {})
        if not data:
            return
        self.add_question(data, record_history=True)
        self.schedule_live_preview_update()

    def toggle_selected_number(self):
        item = self.q_list.currentItem()
        if not item:
            return
        widget = self.q_list.itemWidget(item)
        if not widget:
            return
        show_num_chk = widget.findChild(QCheckBox, "show_num_chk")
        if show_num_chk:
            show_num_chk.setChecked(not show_num_chk.isChecked())

    def adjust_selected_crop(self):
        item = self.q_list.currentItem()
        if not item:
            return
        self.open_inline_crop_adjust(item)

    def open_inline_crop_adjust(self, item):
        data = item.data(Qt.ItemDataRole.UserRole) or {}
        img_path = data.get("img_path", "")
        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "Adjust Crop", "Image file not found for this question.")
            return

        try:
            dlg = InlineCropAdjustDialog(img_path, self)
        except Exception as e:
            QMessageBox.warning(self, "Adjust Crop", f"Could not open editor:\n{e}")
            return

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        self._push_undo_snapshot()
        self._live_preview_cache_hash = None
        widget = self.q_list.itemWidget(item)
        if widget:
            thumb = widget.findChild(QLabel, "thumb")
            if thumb:
                pix = QPixmap(img_path)
                if not pix.isNull():
                    thumb.setPixmap(
                        pix.scaled(
                            self._thumb_w,
                            self._thumb_h,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
        self.update_stats()

    def _set_selected_actions_enabled(self, enabled):
        for btn in (
            self.btn_selected_preview,
            self.btn_selected_edit,
            self.btn_selected_up,
            self.btn_selected_down,
            self.btn_selected_delete,
        ):
            btn.setEnabled(bool(enabled))

    def _apply_item_selection_styles(self):
        current = self.q_list.currentItem()
        for i in range(self.q_list.count()):
            item = self.q_list.item(i)
            widget = self.q_list.itemWidget(item)
            if not widget:
                continue
            is_selected = item is current
            bg = "#EFF6FF" if is_selected else "#FFFFFF"
            border = "#3B82F6" if is_selected else "#E5E7EB"
            widget.setStyleSheet(
                f"QFrame#card {{ background-color: {bg}; border: 2px solid {border}; border-radius: 14px; }}"
            )

    def on_selected_item_changed(self, current, _previous=None):
        if not current:
            self.lbl_selected.setText("Selected: None")
            self._set_selected_actions_enabled(False)
            self._apply_item_selection_styles()
            return

        data = current.data(Qt.ItemDataRole.UserRole) or {}
        qid = str(data.get("id", "Question"))
        topic = str(data.get("topic", "")).strip()
        suffix = f" | Topic: {topic}" if topic else ""
        self.lbl_selected.setText(f"Selected: {qid}{suffix}")
        self._set_selected_actions_enabled(True)
        self._apply_item_selection_styles()

    def _open_preview_dialog(self, img_path, title="Question Preview"):
        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "Preview", "Image file not found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(1080, 780)
        v = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("background-color: #F8FAFC; border: 1px solid #CBD5E1;")
        pix = QPixmap(img_path)
        lbl.setPixmap(
            pix.scaled(1020, 720, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        v.addWidget(lbl)
        dlg.exec()

    def preview_item(self, item):
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole) or {}
        img_path = str(data.get("img_path", "") or "").strip()
        qid = str(data.get("id", "Question"))
        self._open_preview_dialog(img_path, f"Preview - {qid}")

    def preview_selected_item(self):
        self.preview_item(self.q_list.currentItem())

    def update_stats(self):
        count = self.q_list.count()
        total_marks = 0
        for i in range(count):
            item = self.q_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            widget = self.q_list.itemWidget(item)
            if widget:
                order_spin = widget.findChild(QSpinBox, "order_spin")
                if order_spin:
                    order_spin.blockSignals(True)
                    order_spin.setRange(1, max(1, count))
                    order_spin.setValue(i + 1)
                    order_spin.blockSignals(False)
                number_badge = widget.findChild(QLabel, "question_num_badge")
                if number_badge:
                    number_badge.setText(f"No. {i + 1:02d}")
            if data:
                try:
                    total_marks += int(data.get("marks", 0) or 0)
                except Exception:
                    total_marks += 0
        
        self.lbl_stats.setText(f"Total Questions: {count} | Total Marks: {total_marks}")
        self._apply_item_selection_styles()
        if hasattr(self, "_state_save_timer"):
            self._state_save_timer.start()
        else:
            self.save_builder_state()
        self._update_history_buttons()
        self.schedule_live_preview_update()

    def _apply_view_profile(self, mode):
        profile = self._view_profiles.get(mode, self._view_profiles["Compact"])
        self._card_w   = profile["card_w"]
        self._thumb_h  = profile["thumb_h"]
        self._card_margins = profile["margins"]
        self._topic_w  = profile["topic_w"]
        self._order_w  = profile["order_w"]
        self._marks_w  = profile["marks_w"]
        # legacy compat for any code that still references these
        self._thumb_w  = self._card_w
        self._item_h   = self._thumb_h + 90

    def apply_view_size(self, mode):
        self._apply_view_profile(mode)
        for i in range(self.q_list.count()):
            item = self.q_list.item(i)
            item.setSizeHint(QSize(self._card_w + 2, self._thumb_h + 90))
            widget = self.q_list.itemWidget(item)
            if not widget:
                continue
            widget.setFixedWidth(self._card_w)
            layout = widget.layout()
            if layout:
                layout.setContentsMargins(*self._card_margins)
            order_spin = widget.findChild(QSpinBox, "order_spin")
            if order_spin:
                order_spin.setFixedWidth(self._order_w)
            marks_spin = widget.findChild(QSpinBox, "marks_spin")
            if marks_spin:
                marks_spin.setFixedWidth(self._marks_w)
            thumb = widget.findChild(QLabel, "thumb")
            if thumb:
                thumb.setFixedSize(self._thumb_w, self._thumb_h)
                data = item.data(Qt.ItemDataRole.UserRole) or {}
                img_path = data.get("img_path")
                if img_path and os.path.exists(img_path):
                    pix = QPixmap(img_path)
                    if not pix.isNull():
                        thumb.setPixmap(pix.scaled(self._thumb_w, self._thumb_h,
                                                   Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
        self.q_list.update()

    def apply_filter(self, text):
        query = (text or "").strip().lower()
        for i in range(self.q_list.count()):
            item = self.q_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            qid = str(data.get("id", "")).lower()
            topic = str(data.get("topic", "")).lower()
            visible = (query in qid) or (query in topic) if query else True
            item.setHidden(not visible)

    def _current_design_settings(self):
        return {
            "number_style": self.cmb_qnum_style.currentText(),
            "start_number": int(self.spin_start_number.value()),
            "gap_mm": float(self.spin_gap_mm.value()),
            "reverse_order": bool(self.chk_reverse_order.isChecked()),
            "view_size": self.view_size_combo.currentText(),
        }

    def on_design_setting_changed(self, *_args):
        if self._history_suspended:
            return
        self.save_builder_state()
        self.schedule_live_preview_update()

    def _capture_state(self):
        return {
            "saved_at": datetime.now().isoformat(),
            "questions": self.get_questions_in_order(),
            "design": self._current_design_settings(),
        }

    def _restore_state(self, state):
        if not isinstance(state, dict):
            return

        questions = list(state.get("questions", []))
        design = dict(state.get("design", {}))
        if "reverse_order" not in design and "reverse_questions" in state:
            design["reverse_order"] = bool(state.get("reverse_questions", True))

        self._history_suspended = True
        try:
            self.q_list.clear()
            for q in questions:
                self.add_question(q, record_history=False, refresh_ui=False)

            if "view_size" in design:
                self.view_size_combo.setCurrentText(str(design.get("view_size", "Compact")))
            if "reverse_order" in design:
                self.chk_reverse_order.setChecked(bool(design.get("reverse_order", True)))
            if "number_style" in design:
                self.cmb_qnum_style.setCurrentText(str(design.get("number_style", "01.")))
            if "start_number" in design:
                self.spin_start_number.setValue(int(design.get("start_number", 1) or 1))
            if "gap_mm" in design:
                self.spin_gap_mm.setValue(float(design.get("gap_mm", 8.0) or 8.0))
        finally:
            self._history_suspended = False

        self.update_stats()

    def _push_undo_snapshot(self):
        if self._history_suspended:
            return
        self._undo_stack.append(self._capture_state())
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack = self._undo_stack[-self._history_limit :]
        self._redo_stack.clear()
        self._update_history_buttons()

    def _update_history_buttons(self):
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(len(self._undo_stack) > 0)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(len(self._redo_stack) > 0)

    def undo_change(self):
        if not self._undo_stack:
            return
        current = self._capture_state()
        previous = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_state(previous)
        self._update_history_buttons()

    def redo_change(self):
        if not self._redo_stack:
            return
        current = self._capture_state()
        nxt = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_state(nxt)
        self._update_history_buttons()

    def load_design_presets(self):
        presets = {}
        if os.path.exists(self.preset_path):
            try:
                with open(self.preset_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    presets = raw
            except Exception:
                presets = {}

        if not presets:
            presets = {"Default": self._current_design_settings()}
            os.makedirs("config", exist_ok=True)
            with open(self.preset_path, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)

        self.design_presets = presets
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(self.design_presets.keys()))
        self.preset_combo.blockSignals(False)

    def _persist_design_presets(self):
        os.makedirs("config", exist_ok=True)
        with open(self.preset_path, "w", encoding="utf-8") as f:
            json.dump(self.design_presets, f, indent=2, ensure_ascii=False)

    def save_current_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            QMessageBox.warning(self, "Preset", "Preset name is required.")
            return
        self.design_presets[name] = self._current_design_settings()
        self._persist_design_presets()
        self.load_design_presets()
        self.preset_combo.setCurrentText(name)
        QMessageBox.information(self, "Preset Saved", f"Saved preset '{name}'.")

    def apply_selected_preset(self):
        name = self.preset_combo.currentText().strip()
        if not name:
            return
        preset = self.design_presets.get(name)
        if not preset:
            QMessageBox.warning(self, "Preset", "Selected preset was not found.")
            return
        self._push_undo_snapshot()
        self._history_suspended = True
        try:
            self.cmb_qnum_style.setCurrentText(str(preset.get("number_style", "01.")))
            self.spin_start_number.setValue(int(preset.get("start_number", 1) or 1))
            self.spin_gap_mm.setValue(float(preset.get("gap_mm", 8.0) or 8.0))
            self.chk_reverse_order.setChecked(bool(preset.get("reverse_order", True)))
            self.view_size_combo.setCurrentText(str(preset.get("view_size", "Compact")))
        finally:
            self._history_suspended = False
        self.update_stats()
        QMessageBox.information(self, "Preset Applied", f"Applied preset '{name}'.")

    def delete_selected_preset(self):
        name = self.preset_combo.currentText().strip()
        if not name:
            return
        if name == "Default":
            QMessageBox.warning(self, "Preset", "Default preset cannot be deleted.")
            return
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.design_presets.pop(name, None)
        self._persist_design_presets()
        self.load_design_presets()

    def save_snapshot(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ok = QInputDialog.getText(self, "Save Snapshot", "Snapshot name:", text=f"snapshot_{ts}")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return
        os.makedirs(self.snapshot_dir, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
        snap_path = os.path.join(self.snapshot_dir, f"{safe_name}.json")
        asset_dir = os.path.join(self.snapshot_dir, f"{safe_name}_assets")
        payload = self._capture_state()
        payload["name"] = name
        try:
            if os.path.exists(asset_dir):
                shutil.rmtree(asset_dir, ignore_errors=True)
            os.makedirs(asset_dir, exist_ok=True)
            image_backups = []
            for idx, q in enumerate(payload.get("questions", []), 1):
                img_path = str(q.get("img_path", "") or "").strip()
                if not img_path or not os.path.exists(img_path):
                    continue
                ext = os.path.splitext(img_path)[1] or ".png"
                backup_name = f"q_{idx:03d}{ext}"
                backup_path = os.path.join(asset_dir, backup_name)
                try:
                    shutil.copy2(img_path, backup_path)
                    image_backups.append(
                        {
                            "img_path": img_path,
                            "backup_rel_path": os.path.relpath(backup_path, self.snapshot_dir),
                        }
                    )
                except Exception:
                    continue
            payload["_image_backups"] = image_backups

            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self.refresh_snapshot_list(select_path=snap_path)
            QMessageBox.information(self, "Snapshot", f"Saved snapshot '{name}'.")
        except Exception as e:
            QMessageBox.warning(self, "Snapshot", f"Could not save snapshot:\n{e}")

    def refresh_snapshot_list(self, select_path=None):
        os.makedirs(self.snapshot_dir, exist_ok=True)
        files = []
        for name in os.listdir(self.snapshot_dir):
            if name.lower().endswith(".json"):
                files.append(os.path.join(self.snapshot_dir, name))
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        self.snapshot_combo.blockSignals(True)
        self.snapshot_combo.clear()
        for path in files:
            self.snapshot_combo.addItem(os.path.basename(path), path)
        self.snapshot_combo.blockSignals(False)
        if select_path:
            idx = self.snapshot_combo.findData(select_path)
            if idx >= 0:
                self.snapshot_combo.setCurrentIndex(idx)

    def restore_selected_snapshot(self):
        path = self.snapshot_combo.currentData()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Snapshot", "No snapshot selected.")
            return

        reply = QMessageBox.question(
            self,
            "Restore Snapshot",
            "Restore selected snapshot? Current unsaved builder changes will be replaced.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._push_undo_snapshot()
            self._restore_state(payload)
            self._restore_snapshot_images(payload)
            self._live_preview_cache_hash = None
            self.apply_view_size(self.view_size_combo.currentText())
        except Exception as e:
            QMessageBox.warning(self, "Snapshot", f"Failed to restore snapshot:\n{e}")

    def _restore_snapshot_images(self, payload):
        backups = payload.get("_image_backups", [])
        if not isinstance(backups, list):
            return
        for entry in backups:
            try:
                img_path = str(entry.get("img_path", "") or "").strip()
                rel = str(entry.get("backup_rel_path", "") or "").strip()
                if not img_path or not rel:
                    continue
                backup_path = os.path.join(self.snapshot_dir, rel)
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, img_path)
            except Exception:
                continue

    def _load_default_exam_config(self):
        config = {}
        cfg_path = os.path.join("config", "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    app_cfg = json.load(f)
                institute = app_cfg.get("institute", {})
                defaults = app_cfg.get("exam_defaults", {})
                config.update(defaults)
                config["lecturer_name"] = institute.get("lecturer_name", config.get("lecturer_name", "Lecturer"))
                config["lecturer_qualification"] = institute.get(
                    "lecturer_qualification", config.get("lecturer_qualification", "")
                )
                config["logo_path"] = institute.get("logo_path", config.get("logo_path", "logo.png"))
                paper_code = defaults.get("paper_code")
                if isinstance(paper_code, (list, tuple)) and len(paper_code) >= 3:
                    config["paper_code_1"] = str(paper_code[0])
                    config["paper_code_2"] = str(paper_code[1])
                    config["paper_code_3"] = str(paper_code[2])
                config["part_code"] = str(defaults.get("part_code", config.get("paper_code_3", "I")) or "I")
            except Exception:
                pass
        return config

    def _apply_builder_export_options(self, config):
        config["reverse_questions"] = self.chk_reverse_order.isChecked()
        config["start_question_number"] = int(self.spin_start_number.value())

        style_text = self.cmb_qnum_style.currentText().strip()
        style_map = {"01.": "zero_padded", "1.": "plain", "Q1.": "q_prefix"}
        config["question_number_style"] = style_map.get(style_text, "zero_padded")

        layout = dict(config.get("layout", {}))
        layout["question_gap_mm"] = float(self.spin_gap_mm.value())
        config["layout"] = layout
        return config

    def schedule_live_preview_update(self):
        if not hasattr(self, "_live_preview_timer"):
            return
        if not self.chk_auto_live_preview.isChecked():
            return
        self._live_preview_timer.start()

    def change_live_preview_page(self, delta):
        if self._live_preview_total <= 0:
            return
        self._live_preview_page = max(0, min(self._live_preview_total - 1, self._live_preview_page + int(delta)))
        self._render_live_preview_page()

    def _set_live_preview_placeholder(self, text):
        self.lbl_live_preview.setPixmap(QPixmap())
        self.lbl_live_preview.setText(text)
        self.lbl_live_page.setText("Page 0/0")
        self.btn_live_prev.setEnabled(False)
        self.btn_live_next.setEnabled(False)

    def _render_live_preview_page(self):
        if not os.path.exists(self._live_preview_pdf) or self._live_preview_total <= 0:
            self._set_live_preview_placeholder("Preview unavailable.")
            return

        img = PDFToImageConverter.convert_page(self._live_preview_pdf, self._live_preview_page, dpi=130)
        if not img:
            self._set_live_preview_placeholder("Could not render preview page.")
            return
        if img.mode != "RGB":
            img = img.convert("RGB")
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.lbl_live_preview.setPixmap(
            pix.scaled(
                self.lbl_live_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.lbl_live_page.setText(f"Page {self._live_preview_page + 1}/{self._live_preview_total}")
        self.btn_live_prev.setEnabled(self._live_preview_page > 0)
        self.btn_live_next.setEnabled(self._live_preview_page < self._live_preview_total - 1)

    def refresh_live_preview(self, force=False):
        questions = self.get_questions_in_order()
        if not questions:
            self._live_preview_cache_hash = None
            self._live_preview_total = 0
            self._live_preview_page = 0
            self._set_live_preview_placeholder("Add questions to generate live preview.")
            return

        config = self._apply_builder_export_options(self._load_default_exam_config())
        cache_payload = {"questions": questions, "config": config}
        try:
            cache_hash = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            cache_hash = str(datetime.now().timestamp())

        needs_render = force or (cache_hash != self._live_preview_cache_hash) or (not os.path.exists(self._live_preview_pdf))
        if needs_render:
            ok = PDFExporter.generate_exam_pdf(questions, self._live_preview_pdf, config=config)
            if not ok:
                self._set_live_preview_placeholder("Failed to generate preview.")
                return
            self._live_preview_cache_hash = cache_hash
            self._live_preview_total = max(0, PDFToImageConverter.get_page_count(self._live_preview_pdf))
            if self._live_preview_total <= 0:
                self._set_live_preview_placeholder("Preview PDF has no pages.")
                return
            self._live_preview_page = max(0, min(self._live_preview_page, self._live_preview_total - 1))

        self._render_live_preview_page()

    def save_builder_state(self):
        self._save_builder_state_now()

    def _save_builder_state_now(self):
        try:
            os.makedirs("config", exist_ok=True)
            data = self._capture_state()
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def load_builder_state(self):
        if not os.path.exists(self.state_path):
            return False
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            questions = data.get("questions", [])
            if not questions:
                return False
            self._restore_state(data)
            return True
        except Exception:
            return False

    def get_questions_in_order(self):
        questions = []
        for i in range(self.q_list.count()):
            item = self.q_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            widget = self.q_list.itemWidget(item)
            if widget:
                topic = widget.findChild(QLineEdit, "topic_edit")
                marks = widget.findChild(QSpinBox, "marks_spin")
                show_num_chk = widget.findChild(QCheckBox, "show_num_chk")
                if topic:
                    data["topic"] = topic.text()
                if marks:
                    data["marks"] = int(marks.value())
                if show_num_chk:
                    data["show_number"] = bool(show_num_chk.isChecked())
            questions.append(dict(data))
        return questions

    def handle_export(self):
        if self.q_list.count() == 0:
            QMessageBox.warning(self, "Export Failed", "Please add some questions first.")
            return

        from src.ui.exam_config_dialog import ExamConfigDialog
        config_dialog = ExamConfigDialog(self)

        def on_config_accepted(config):
            path, _ = QFileDialog.getSaveFileName(self, "Export Exam PDF", "", "PDF Files (*.pdf)")
            if not path:
                return

            config = self._apply_builder_export_options(config)
            questions = self.get_questions_in_order()

            try:
                if PDFExporter.generate_exam_pdf(questions, path, config=config):
                    QMessageBox.information(self, "Success", f"Exam exported successfully to:\n{path}")
                    self.record_export(path)
                    try:
                        os.startfile(path)
                    except:
                        pass
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate PDF: {str(e)}")

        config_dialog.config_accepted.connect(on_config_accepted)
        config_dialog.exec()

    def handle_test_export(self):
        from src.ui.exam_config_dialog import ExamConfigDialog
        config_dialog = ExamConfigDialog(self)

        def on_config_accepted(config):
            path, _ = QFileDialog.getSaveFileName(self, "Export Header Test PDF", "", "PDF Files (*.pdf)")
            if not path:
                return
            config = self._apply_builder_export_options(config)
            try:
                if PDFExporter.generate_exam_pdf([], path, config=config):
                    QMessageBox.information(self, "Success", f"Header test exported to:\n{path}")
                    self.record_export(path)
                    try:
                        os.startfile(path)
                    except:
                        pass
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate test PDF: {str(e)}")

        config_dialog.config_accepted.connect(on_config_accepted)
        config_dialog.exec()

    def handle_preview_header(self):
        from src.ui.exam_config_dialog import ExamConfigDialog
        from src.utils.converter import PDFToImageConverter

        config_dialog = ExamConfigDialog(self)

        def on_config_accepted(config):
            tmp_dir = tempfile.gettempdir()
            tmp_pdf = os.path.join(tmp_dir, "exam_header_preview.pdf")
            config = self._apply_builder_export_options(config)
            try:
                config_hash = json.dumps(config, sort_keys=True)
                if self._preview_cache.get("hash") != config_hash or not os.path.exists(tmp_pdf):
                    if not PDFExporter.generate_exam_pdf([], tmp_pdf, config=config):
                        QMessageBox.warning(self, "Preview Failed", "Could not generate preview PDF.")
                        return
                    self._preview_cache["hash"] = config_hash
                    self._preview_cache["path"] = tmp_pdf
                img = PDFToImageConverter.convert_page(tmp_pdf, 0, dpi=150)
                if not img:
                    QMessageBox.warning(self, "Preview Failed", "Could not render preview.")
                    return
                if img.mode != "RGB":
                    img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                w, h = img.size
                qimage = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimage)

                dlg = QDialog(self)
                dlg.setWindowTitle("Header Preview")
                dlg.resize(900, 500)
                v = QVBoxLayout(dlg)
                lbl = QLabel()
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setPixmap(pix.scaled(860, 460, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
                v.addWidget(lbl)
                # Slide-in animation
                geom = dlg.geometry()
                start = geom
                start.moveTop(geom.top() + 20)
                dlg.setGeometry(start)
                anim = QPropertyAnimation(dlg, b"geometry", dlg)
                anim.setDuration(220)
                anim.setStartValue(start)
                anim.setEndValue(geom)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()
                dlg._slide_anim = anim
                dlg.exec()
            except Exception as e:
                QMessageBox.critical(self, "Preview Error", f"Failed to render preview: {str(e)}")

        config_dialog.config_accepted.connect(on_config_accepted)
        config_dialog.exec()

    def handle_export_docx(self):
        if self.q_list.count() == 0:
            QMessageBox.warning(self, "Export Failed", "Please add some questions first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Exam DOCX", "", "Word Files (*.docx)")
        if not path:
            return

        questions = self.get_questions_in_order()

        try:
            if PDFExporter.generate_exam_docx(questions, path):
                QMessageBox.information(self, "Success", f"Exam exported successfully to:\n{path}")
                self.record_export(path)
                try:
                    os.startfile(path)
                except:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate Word document: {str(e)}")

    def handle_export_key(self):
        if self.q_list.count() == 0:
            QMessageBox.warning(self, "Export Failed", "Please add some questions first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Answer Key PDF", "", "PDF Files (*.pdf)")
        if not path:
            return

        questions = self.get_questions_in_order()

        try:
            if PDFExporter.generate_answer_key_pdf(questions, path):
                QMessageBox.information(self, "Success", f"Answer Key exported to:\n{path}")
                self.record_export(path)
                try:
                    os.startfile(path)
                except:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed: {str(e)}")

    def load_export_history(self):
        path = os.path.join("config", "export_history.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.export_history = json.load(f)
            except Exception:
                self.export_history = []
        self.update_export_ui()

    def record_export(self, path):
        entry = {"path": path, "timestamp": datetime.now().isoformat()}
        self.export_history = [entry] + [e for e in self.export_history if e.get("path") != path]
        self.export_history = self.export_history[:5]
        os.makedirs("config", exist_ok=True)
        with open(os.path.join("config", "export_history.json"), "w", encoding="utf-8") as f:
            json.dump(self.export_history, f, indent=2, ensure_ascii=False)
        self.update_export_ui()

    def update_export_ui(self):
        if self.export_history:
            last = self.export_history[0].get("path", "")
            self.lbl_last_export.setText(f"Last Export: {last}")
            self.btn_open_last.setEnabled(True)
        else:
            self.lbl_last_export.setText("Last Export: None")
            self.btn_open_last.setEnabled(False)

    def open_last_export(self):
        if not self.export_history:
            return
        last = self.export_history[0].get("path")
        if last and os.path.exists(last):
            try:
                os.startfile(last)
            except Exception:
                QMessageBox.warning(self, "Open Failed", "Could not open the last export.")

    def on_show(self):
        if self.q_list.count() == 0 and os.path.exists(self.state_path):
            res = QMessageBox.question(
                self,
                "Restore Last Session",
                "Load your last builder session?"
            )
            if res == QMessageBox.StandardButton.Yes:
                self.load_builder_state()
        self.refresh_snapshot_list()
        self.schedule_live_preview_update()

