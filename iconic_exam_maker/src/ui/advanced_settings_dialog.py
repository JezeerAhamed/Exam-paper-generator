import json
import logging
import os
import tempfile
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QGroupBox, QScrollArea, QWidget, QDoubleSpinBox, QSpinBox, QLineEdit,
    QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QImage, QPixmap
from src.utils.exporter import PDFExporter
from src.utils.converter import PDFToImageConverter

_logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join("config", "config.json")


class AdvancedSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Layout Settings")
        self.resize(520, 640)
        self.setModal(True)
        self.defaults = self._load_defaults()
        self.widgets = {}
        self.search_rows = []
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.init_ui()

    def _load_defaults(self):
        defaults = {
            "footer_quote": "“Find simplicity in the universe”",
            "layout_defaults": {
                "border_margin_mm": 10,
                "border_radius_pt": 15,
                "border_width_pt": 2,
                "row1_h_mm": 22,
                "logo_w_mm": 50,
                "logo_h_mm": 18,
                "logo_radius_pt": 8,
                "logo_border_pt": 1,
                "logo_inner_pad_pt": 2,
                "logo_inner_radius_pt": 6,
                "logo_inner_border_pt": 0.8,
                "logo_pad_w_mm": 3,
                "logo_pad_h_mm": 2,
                "num_box_size_mm": 14,
                "num_box_radius_pt": 7,
                "num_box_border_pt": 1,
                "row2_h_mm": 12,
                "lang_box_w_mm": 34,
                "lang_box_radius_pt": 6,
                "lang_box_border_pt": 1,
                "code_base_offset_mm": 14,
                "code_w_mm": 10,
                "code_spacing_mm": 1.5,
                "code_radius_pt": 6,
                "code_outer_border_pt": 2,
                "code_inner_radius_pt": 4,
                "code_inner_border_pt": 1,
                "time_right_pad_mm": 5,
                "row3_h_mm": 17,
                "const_w_mm": 66,
                "const_radius_pt": 6,
                "const_border_pt": 1.5,
                "const_row_step_mm": 3.6,
                "const_desc_x_mm": 3,
                "const_sym_x_mm": 34,
                "const_eq_x_mm": 39,
                "const_val_x_mm": 45,
                "marks_box_w_mm": 10,
                "marks_gap_mm": 4,
                "marks_radius_pt": 6,
                "marks_border_pt": 1,
                "footer_font_size": 9,
                "footer_text_offset_pt": 3,
                "footer_line_gap_pt": 2,
                "footer_side_pad_pt": 10
            },
            "layout_presets": {}
        }

        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                defaults["footer_quote"] = data.get("exam_defaults", {}).get(
                    "footer_quote", defaults["footer_quote"]
                )
                defaults["layout_defaults"].update(data.get("layout_defaults", {}))
                defaults["layout_presets"] = data.get("layout_presets", {})
                defaults["detection"] = data.get("detection", {})
            except (OSError, json.JSONDecodeError) as e:
                _logger.warning("Settings read failed: %s", e)

        return defaults

    def _add_group(self, parent_layout, title, fields):
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setSpacing(8)

        for key, label, step, min_v, max_v in fields:
            label_widget = QLabel(label)
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setSingleStep(step)
            spin.setRange(min_v, max_v)
            spin.setValue(float(self.defaults["layout_defaults"].get(key, 0)))
            self.widgets[key] = spin
            form.addRow(label_widget, spin)
            self.search_rows.append((label_widget, spin, group))
            spin.valueChanged.connect(self.queue_preview)

        parent_layout.addWidget(group)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Advanced Layout Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("Adjust layout measurements. Defaults match the current design.")
        desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(desc)

        top_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search settings...")
        self.search_input.textChanged.connect(self.apply_search_filter)
        top_row.addWidget(self.search_input)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Current (Default)")
        for name in sorted(self.defaults.get("layout_presets", {}).keys()):
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        top_row.addWidget(self.preset_combo)

        self.preset_name = QLineEdit()
        self.preset_name.setPlaceholderText("Preset name")
        self.preset_name.setFixedWidth(140)
        top_row.addWidget(self.preset_name)

        save_preset_btn = QPushButton("Save Preset")
        save_preset_btn.clicked.connect(self.save_preset)
        top_row.addWidget(save_preset_btn)

        layout.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)

        quote_group = QGroupBox("Footer Quote")
        quote_form = QFormLayout(quote_group)
        self.quote_input = QLineEdit(self.defaults["footer_quote"])
        quote_form.addRow("Quote:", self.quote_input)
        self.quote_input.textChanged.connect(self.queue_preview)
        content_layout.addWidget(quote_group)

        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_toggle = QCheckBox("Enable live preview")
        self.preview_toggle.setChecked(True)
        self.preview_toggle.stateChanged.connect(self.queue_preview)
        preview_layout.addWidget(self.preview_toggle)
        self.preview_label = QLabel()
        self.preview_label.setFixedHeight(220)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0;")
        preview_layout.addWidget(self.preview_label)
        content_layout.addWidget(preview_group)

        self._add_group(
            content_layout,
            "Page & Border",
            [
                ("border_margin_mm", "Border Margin (mm):", 0.5, 2, 30),
                ("border_radius_pt", "Border Radius (pt):", 0.5, 2, 40),
                ("border_width_pt", "Border Width (pt):", 0.5, 0.5, 6),
            ],
        )

        self._add_group(
            content_layout,
            "Header",
            [
                ("row1_h_mm", "Row 1 Height (mm):", 0.5, 10, 40),
                ("logo_w_mm", "Logo Width (mm):", 0.5, 20, 80),
                ("logo_h_mm", "Logo Height (mm):", 0.5, 10, 40),
                ("logo_radius_pt", "Logo Radius (pt):", 0.5, 2, 20),
                ("logo_border_pt", "Logo Border (pt):", 0.5, 0.5, 4),
                ("logo_inner_pad_pt", "Logo Inner Pad (pt):", 0.5, 0, 10),
                ("logo_inner_radius_pt", "Logo Inner Radius (pt):", 0.5, 2, 20),
                ("logo_inner_border_pt", "Logo Inner Border (pt):", 0.1, 0.2, 3),
                ("logo_pad_w_mm", "Logo Pad W (mm):", 0.5, 0, 10),
                ("logo_pad_h_mm", "Logo Pad H (mm):", 0.5, 0, 10),
                ("num_box_size_mm", "Paper No Box (mm):", 0.5, 8, 30),
                ("num_box_radius_pt", "Paper No Radius (pt):", 0.5, 2, 20),
                ("num_box_border_pt", "Paper No Border (pt):", 0.5, 0.5, 4),
            ],
        )

        self._add_group(
            content_layout,
            "Row 2",
            [
                ("row2_h_mm", "Row 2 Height (mm):", 0.5, 6, 25),
                ("lang_box_w_mm", "Language Box Width (mm):", 0.5, 20, 60),
                ("lang_box_radius_pt", "Lang Box Radius (pt):", 0.5, 2, 20),
                ("lang_box_border_pt", "Lang Box Border (pt):", 0.5, 0.5, 4),
                ("code_base_offset_mm", "Code Base Offset (mm):", 0.5, 5, 30),
                ("code_w_mm", "Code Box Size (mm):", 0.5, 6, 20),
                ("code_spacing_mm", "Code Box Spacing (mm):", 0.5, 0.5, 10),
                ("code_radius_pt", "Code Radius (pt):", 0.5, 2, 20),
                ("code_outer_border_pt", "Code Outer Border (pt):", 0.5, 0.5, 4),
                ("code_inner_radius_pt", "Code Inner Radius (pt):", 0.5, 2, 20),
                ("code_inner_border_pt", "Code Inner Border (pt):", 0.5, 0.5, 4),
                ("time_right_pad_mm", "Time Right Pad (mm):", 0.5, 0, 15),
            ],
        )

        self._add_group(
            content_layout,
            "Row 3",
            [
                ("row3_h_mm", "Row 3 Height (mm):", 0.5, 8, 30),
                ("const_w_mm", "Constants Box Width (mm):", 0.5, 40, 120),
                ("const_radius_pt", "Constants Radius (pt):", 0.5, 2, 20),
                ("const_border_pt", "Constants Border (pt):", 0.5, 0.5, 4),
                ("const_row_step_mm", "Constants Row Step (mm):", 0.1, 1, 10),
                ("const_desc_x_mm", "Const Desc X (mm):", 0.5, 0, 20),
                ("const_sym_x_mm", "Const Sym X (mm):", 0.5, 10, 60),
                ("const_eq_x_mm", "Const Eq X (mm):", 0.5, 10, 70),
                ("const_val_x_mm", "Const Val X (mm):", 0.5, 10, 80),
                ("marks_box_w_mm", "Marks Box Width (mm):", 0.5, 6, 25),
                ("marks_gap_mm", "Marks Gap (mm):", 0.5, 1, 15),
                ("marks_radius_pt", "Marks Radius (pt):", 0.5, 2, 20),
                ("marks_border_pt", "Marks Border (pt):", 0.5, 0.5, 4),
            ],
        )

        self._add_group(
            content_layout,
            "Footer",
            [
                ("footer_font_size", "Footer Font Size:", 1, 6, 20),
                ("footer_text_offset_pt", "Footer Text Offset (pt):", 0.5, 0, 10),
                ("footer_line_gap_pt", "Footer Line Gap (pt):", 0.5, 0, 10),
                ("footer_side_pad_pt", "Footer Side Pad (pt):", 0.5, 0, 20),
            ],
        )

        # Detection Parameters group
        detection_group = QGroupBox("Detection Parameters")
        detection_form = QFormLayout(detection_group)
        detection_form.setSpacing(8)

        self.spin_min_score = QSpinBox()
        self.spin_min_score.setRange(0, 100)
        self.spin_min_score.setValue(60)
        detection_form.addRow("Min detection score:", self.spin_min_score)

        self.spin_mcq_min_w = QSpinBox()
        self.spin_mcq_min_w.setRange(50, 500)
        self.spin_mcq_min_w.setValue(200)
        detection_form.addRow("MCQ min width (px):", self.spin_mcq_min_w)

        self.spin_mcq_min_h = QSpinBox()
        self.spin_mcq_min_h.setRange(20, 200)
        self.spin_mcq_min_h.setValue(100)
        detection_form.addRow("MCQ min height (px):", self.spin_mcq_min_h)

        content_layout.addWidget(detection_group)

        # Load detection values from config
        detection_cfg = self.defaults.get("detection", {})
        self.spin_min_score.setValue(detection_cfg.get("min_score", 60))
        self.spin_mcq_min_w.setValue(detection_cfg.get("mcq_min_w", 200))
        self.spin_mcq_min_h.setValue(detection_cfg.get("mcq_min_h", 100))

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_defaults)
        btn_row.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("success")
        save_btn.clicked.connect(self.save_settings)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        self.queue_preview()

    def showEvent(self, event):
        super().showEvent(event)
        # Slide-in animation
        geom = self.geometry()
        start = geom
        start.moveTop(geom.top() + 20)
        self.setGeometry(start)
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(220)
        anim.setStartValue(start)
        anim.setEndValue(geom)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._slide_anim = anim

    def save_settings(self):
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                _logger.warning("Settings read failed: %s", e)
                data = {}

        data.setdefault("exam_defaults", {})
        data.setdefault("layout_defaults", {})

        data["exam_defaults"]["footer_quote"] = self.quote_input.text().strip() or self.defaults["footer_quote"]
        for key, widget in self.widgets.items():
            data["layout_defaults"][key] = float(widget.value())

        data["detection"] = {
            "min_score": self.spin_min_score.value(),
            "mcq_min_w": self.spin_mcq_min_w.value(),
            "mcq_min_h": self.spin_mcq_min_h.value(),
        }

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.accept()

    def queue_preview(self):
        if not self.preview_toggle.isChecked():
            return
        self.preview_timer.start(400)

    def refresh_preview(self):
        try:
            config = {
                "subject": "PHYSICS",
                "exam_series": "Final Exam Series",
                "paper_number": "1",
                "duration": "01 hour",
                "paper_code_1": "01",
                "paper_code_2": "T",
                "paper_code_3": "I",
                "lecturer_name": "M.M.JEZEER AHAMED",
                "lecturer_qualification": "B.sc (Engineering)",
                "logo_path": "logo.png",
                "footer_quote": self.quote_input.text().strip() or self.defaults["footer_quote"],
                "layout": {k: float(w.value()) for k, w in self.widgets.items()}
            }
            tmp_pdf = os.path.join(tempfile.gettempdir(), "advanced_preview.pdf")
            if PDFExporter.generate_exam_pdf([], tmp_pdf, config=config):
                img = PDFToImageConverter.convert_page(tmp_pdf, 0, dpi=120)
                if not img:
                    return
                if img.mode != "RGB":
                    img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                w, h = img.size
                qimage = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimage)
                self.preview_label.setPixmap(
                    pix.scaled(self.preview_label.width(), self.preview_label.height(),
                               Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
        except Exception as e:
            _logger.warning("Settings read failed: %s", e)

    def apply_search_filter(self, text):
        term = text.strip().lower()
        for label, field, group in self.search_rows:
            visible = term == "" or term in label.text().lower()
            label.setVisible(visible)
            field.setVisible(visible)
        for _, _, group in self.search_rows:
            has_visible = False
            for i in range(group.layout().rowCount()):
                label_item = group.layout().itemAt(i, QFormLayout.ItemRole.LabelRole)
                field_item = group.layout().itemAt(i, QFormLayout.ItemRole.FieldRole)
                if label_item and field_item and label_item.widget().isVisible() and field_item.widget().isVisible():
                    has_visible = True
                    break
            group.setVisible(has_visible or term == "")

    def apply_preset(self, name):
        presets = self.defaults.get("layout_presets", {})
        if name in presets:
            preset = presets[name]
            for key, widget in self.widgets.items():
                if key in preset:
                    widget.setValue(float(preset[key]))
            self.queue_preview()

    def save_preset(self):
        name = self.preset_name.text().strip()
        if not name:
            return
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                _logger.warning("Settings read failed: %s", e)
                data = {}
        data.setdefault("layout_presets", {})
        data["layout_presets"][name] = {k: float(w.value()) for k, w in self.widgets.items()}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if self.preset_combo.findText(name) == -1:
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(name)

    def reset_defaults(self):
        for key, widget in self.widgets.items():
            widget.setValue(float(self.defaults["layout_defaults"].get(key, 0)))
        self.quote_input.setText(self.defaults["footer_quote"])
        self.queue_preview()
