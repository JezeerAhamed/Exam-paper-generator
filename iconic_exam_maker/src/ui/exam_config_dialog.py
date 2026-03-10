import json
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QComboBox, QFormLayout,
                               QGroupBox, QFrame, QScrollArea, QWidget, QTableWidget,
                               QTableWidgetItem, QHeaderView, QMessageBox, QSpinBox,
                               QCheckBox, QGridLayout, QSizePolicy, QDoubleSpinBox)
from PySide6.QtCore import Qt, Signal, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QFont

SUBJECTS_CONFIG_PATH = os.path.join("config", "subjects.json")


# ─────────────────────────────────────────────────────────────────────────────
# Custom Toggle Switch widget
# ─────────────────────────────────────────────────────────────────────────────
class ToggleSwitch(QPushButton):
    """An iOS-style toggle switch."""
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = QColor("#f97316") if self.isChecked() else QColor("#CBD5E1")
        p.setBrush(track_color)
        p.setPen(Qt.PenStyle.NoPen)
        track = QRectF(0, 3, 46, 20)
        p.drawRoundedRect(track, 10, 10)

        p.setBrush(QColor("#FFFFFF"))
        handle_x = 24.0 if self.isChecked() else 2.0
        p.drawEllipse(QRectF(handle_x, 1, 24, 24))
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Section card widget helper
# ─────────────────────────────────────────────────────────────────────────────
def _section_card(title: str) -> tuple:
    """Returns (card_frame, inner_layout) for a titled section card."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB;"
        " border-radius: 8px; }"
    )
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(20, 16, 20, 20)
    outer.setSpacing(14)

    lbl = QLabel(title)
    lbl.setStyleSheet(
        "font-size: 11px; font-weight: 700; color: #9CA3AF;"
        " letter-spacing: 1px; border: none; background: transparent;"
    )
    outer.addWidget(lbl)
    return frame, outer


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; border: none;")
    return lbl


_INPUT_STYLE = (
    "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {"
    " min-height: 36px; border: 1px solid #D1D5DB; border-radius: 6px;"
    " padding: 0 10px; background: #FFFFFF; color: #111827; font-size: 13px; }"
    "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {"
    " border-color: #f97316; outline: none; }"
)


# ─────────────────────────────────────────────────────────────────────────────
class SubjectManagerDialog(QDialog):
    """Dialog to manage subjects and their translations"""
    subjects_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Subjects")
        self.resize(600, 400)
        self.setModal(True)
        self.setStyleSheet("QDialog { background: #F9FAFB; }")
        self.init_ui()
        self.load_subjects()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Subject (English)", "Sinhala", "Tamil"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Input Form
        form_layout = QHBoxLayout()
        self.input_eng = QLineEdit()
        self.input_eng.setPlaceholderText("English (e.g. MATHS)")
        self.input_sin = QLineEdit()
        self.input_sin.setPlaceholderText("Sinhala Translation")
        self.input_tam = QLineEdit()
        self.input_tam.setPlaceholderText("Tamil Translation")

        add_btn = QPushButton("Add / Update")
        add_btn.clicked.connect(self.save_subject)
        add_btn.setStyleSheet(
            "background-color: #1473E6; color: white; font-weight: 600;"
            " border-radius: 3px; border: none; padding: 6px 14px;"
        )

        form_layout.addWidget(self.input_eng)
        form_layout.addWidget(self.input_sin)
        form_layout.addWidget(self.input_tam)
        form_layout.addWidget(add_btn)
        layout.addLayout(form_layout)

        layout.addWidget(QLabel("Tip: Select a row to delete it."))

        del_btn = QPushButton("Delete Selected Subject")
        del_btn.setStyleSheet(
            "background-color: #FFFFFF; color: #CC0000; border: 1px solid #CC0000;"
            " border-radius: 3px; font-weight: 600; padding: 6px 14px;"
        )
        del_btn.clicked.connect(self.delete_subject)
        layout.addWidget(del_btn)

    def load_subjects(self):
        self.table.setRowCount(0)
        if os.path.exists(SUBJECTS_CONFIG_PATH):
            with open(SUBJECTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

            for row, (subj, trans) in enumerate(self.data.items()):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(subj))
                self.table.setItem(row, 1, QTableWidgetItem(trans.get('sinhala', '')))
                self.table.setItem(row, 2, QTableWidgetItem(trans.get('tamil', '')))

    def save_subject(self):
        eng = self.input_eng.text().strip().upper()
        sin = self.input_sin.text().strip()
        tam = self.input_tam.text().strip()

        if not eng:
            QMessageBox.warning(self, "Error", "Subject name is required.")
            return

        if os.path.exists(SUBJECTS_CONFIG_PATH):
            with open(SUBJECTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        data[eng] = {"sinhala": sin, "tamil": tam}

        with open(SUBJECTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.load_subjects()
        self.input_eng.clear()
        self.input_sin.clear()
        self.input_tam.clear()
        self.subjects_updated.emit()

    def delete_subject(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            return

        subj = self.table.item(curr_row, 0).text()

        if os.path.exists(SUBJECTS_CONFIG_PATH):
            with open(SUBJECTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if subj in data:
                del data[subj]

            with open(SUBJECTS_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        self.load_subjects()
        self.subjects_updated.emit()


# ─────────────────────────────────────────────────────────────────────────────
class ExamConfigDialog(QDialog):
    """
    Exam configuration dialog — redesigned to match the Admin Panel reference UI.
    Sections: Paper Identity | Typography | Lecturer Details | Page Formatting
    """
    config_accepted = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exam Configuration")
        self.resize(1020, 760)
        self.setMinimumSize(900, 680)
        self.setModal(True)

        self.defaults = self.load_defaults()
        self.init_ui()

    # ── Defaults loading ──────────────────────────────────────────────────────
    def load_defaults(self):
        config_path = os.path.join("config", "config.json")
        defaults = {
            "subject": "PHYSICS",
            "exam_series": "Final Semester Assessment",
            "paper_number": "1",
            "duration": "120",
            "paper_code": ["01", "T", "I"],
            "part_code": "I",
            "lecturer_name": "M.M.JEZEER AHAMED",
            "lecturer_qualification": "B.sc (Engineering)",
            "logo_path": "logo.png",
            "footer_quote": "Find simplicity in the universe.",
            "show_page_numbers": True,
            "start_question_number": 1,
            "layout": {},
            "font_sizes": {
                "adv_level": 18, "subject_header": 32, "series": 16,
                "paper_num": 40, "box_labels": 13, "paper_code": 16,
                "time": 14, "instructions": 25, "constants": 22,
                "lecturer": 14, "lecturer_qual": 12, "question_num": 16, "footer": 12
            }
        }
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                if "exam_defaults" in config:
                    defaults.update(config["exam_defaults"])
                if "layout_defaults" in config:
                    defaults["layout"] = config.get("layout_defaults", defaults.get("layout", {}))
                if "institute" in config:
                    defaults["lecturer_name"] = config["institute"].get("lecturer_name", defaults["lecturer_name"])
                    defaults["lecturer_qualification"] = config["institute"].get("lecturer_qualification", defaults["lecturer_qualification"])
                    defaults["logo_path"] = config["institute"].get("logo_path", defaults["logo_path"])
        except Exception as e:
            print(f"Error loading config: {e}")

        paper_codes = defaults.get("paper_code", ["01", "T", "I"])
        if not isinstance(paper_codes, list):
            paper_codes = ["01", "T", "I"]
        while len(paper_codes) < 3:
            paper_codes.append("I" if len(paper_codes) == 2 else "")
        defaults["paper_code"] = paper_codes
        defaults["part_code"] = str(defaults.get("part_code", paper_codes[2] or "I") or "I")
        defaults["footer_quote"] = self._normalize_quote(defaults.get("footer_quote", "Find simplicity in the universe."))
        return defaults

    def _normalize_quote(self, text):
        quote = str(text or "").strip()
        quote = quote.replace("â€œ", '"').replace("â€", '"')
        return quote or "Find simplicity in the universe."

    def _save_defaults_to_config(self, footer_quote, part_code):
        config_path = os.path.join("config", "config.json")
        data = {}
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception:
            data = {}

        data.setdefault("exam_defaults", {})
        data["exam_defaults"]["footer_quote"] = footer_quote
        data["exam_defaults"]["show_page_numbers"] = bool(self.toggle_page_numbers.isChecked())
        data["exam_defaults"]["start_question_number"] = int(self.start_qnum_spin.value())
        data["exam_defaults"]["paper_code"] = [
            self.code1_input.text().strip() or "01",
            self.code2_input.text().strip() or "T",
            part_code,
        ]
        data["exam_defaults"]["part_code"] = part_code

        try:
            os.makedirs("config", exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: could not save exam defaults: {e}")

    # ── UI Construction ───────────────────────────────────────────────────────
    def init_ui(self):
        self.setStyleSheet(
            "QDialog { background-color: #F3F4F6; }"
            + _INPUT_STYLE +
            "QLabel { border: none; background: transparent; }"
            "QPushButton { font-size: 13px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Page Header ───────────────────────────────────────────────────────
        page_header = QWidget()
        page_header.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E5E7EB;")
        ph_layout = QVBoxLayout(page_header)
        ph_layout.setContentsMargins(32, 20, 32, 20)
        ph_layout.setSpacing(4)

        title_lbl = QLabel("Exam Configuration")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 700; color: #111827;")
        ph_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Define the visual identity and structural metadata for the generated examination papers.")
        subtitle_lbl.setStyleSheet("font-size: 13px; color: #6B7280;")
        ph_layout.addWidget(subtitle_lbl)
        root.addWidget(page_header)

        # ── Scrollable Content ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(32, 24, 32, 24)
        cv.setSpacing(16)

        # ── Row 1: Paper Identity  |  Typography Controls ─────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # — Paper Identity ——
        pi_card, pi_layout = _section_card("PAPER IDENTITY")
        pi_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        pi_layout.addWidget(_field_label("Exam Title"))
        subject_row = QHBoxLayout()
        subject_row.setSpacing(8)
        self.subject_combo = QComboBox()
        self.populate_subjects()
        self.subject_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        subject_row.addWidget(self.subject_combo)
        manage_btn = QPushButton("Manage")
        manage_btn.setFixedHeight(36)
        manage_btn.setFixedWidth(90)
        manage_btn.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #1473E6; border: 1px solid #1473E6;"
            " border-radius: 6px; font-weight: 600; }"
            "QPushButton:hover { background: #DDEEFE; }"
        )
        manage_btn.clicked.connect(self.open_subject_manager)
        subject_row.addWidget(manage_btn)
        pi_layout.addLayout(subject_row)

        pi_layout.addWidget(_field_label("Exam Series / Title"))
        self.series_input = QLineEdit(self.defaults.get("exam_series", "Final Semester Assessment"))
        self.series_input.setPlaceholderText("e.g. Final Semester Assessment")
        pi_layout.addWidget(self.series_input)

        pi_layout.addWidget(_field_label("Paper Code Structure"))
        code_row = QHBoxLayout()
        code_row.setSpacing(8)
        paper_codes = self.defaults.get("paper_code", ["01", "T", "I"])
        self.code1_input = QLineEdit(paper_codes[0] if len(paper_codes) > 0 else "01")
        self.code1_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code1_input.setPlaceholderText("01")
        code_row.addWidget(self.code1_input)
        self.code2_input = QLineEdit(paper_codes[1] if len(paper_codes) > 1 else "T")
        self.code2_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code2_input.setPlaceholderText("T")
        code_row.addWidget(self.code2_input)
        self.code3_input = QLineEdit(self.defaults.get("part_code", paper_codes[2] if len(paper_codes) > 2 else "I"))
        self.code3_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code3_input.setPlaceholderText("I")
        self.code3_input.setToolTip("Part code (e.g. I, II, 1, 2)")
        code_row.addWidget(self.code3_input)
        pi_layout.addLayout(code_row)

        fmt_hint = QLabel("Format: {ID}-{Type}-{Version}")
        fmt_hint.setStyleSheet("font-size: 11px; color: #9CA3AF; border: none;")
        pi_layout.addWidget(fmt_hint)

        dur_marks_row = QHBoxLayout()
        dur_marks_row.setSpacing(12)
        dur_col = QVBoxLayout()
        dur_col.addWidget(_field_label("Duration (Min)"))
        self.duration_input = QLineEdit(str(self.defaults.get("duration", "120")).replace(" hour", "").replace("hour", ""))
        self.duration_input.setPlaceholderText("120")
        dur_col.addWidget(self.duration_input)
        dur_marks_row.addLayout(dur_col)

        marks_col = QVBoxLayout()
        marks_col.addWidget(_field_label("Start Question №"))
        self.start_qnum_spin = QSpinBox()
        self.start_qnum_spin.setRange(1, 9999)
        self.start_qnum_spin.setValue(int(self.defaults.get("start_question_number", 1)))
        marks_col.addWidget(self.start_qnum_spin)
        dur_marks_row.addLayout(marks_col)
        pi_layout.addLayout(dur_marks_row)

        pi_layout.addWidget(_field_label("Footer Quote"))
        self.footer_quote_input = QLineEdit(self.defaults.get("footer_quote", "Find simplicity in the universe."))
        self.footer_quote_input.setPlaceholderText("Footer quote")
        self.footer_quote_input.setClearButtonEnabled(True)
        pi_layout.addWidget(self.footer_quote_input)

        row1.addWidget(pi_card, 3)

        # — Typography Controls ——
        ty_card, ty_layout = _section_card("TYPOGRAPHY CONTROLS")
        ty_card.setFixedWidth(320)

        # Header row for the mini table
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(0)
        for col_txt, stretch in [("ELEMENT", 2), ("SIZE (PT)", 1)]:
            h = QLabel(col_txt)
            h.setStyleSheet("font-size: 10px; font-weight: 700; color: #9CA3AF; border: none;")
            hdr_row.addWidget(h, stretch)
        ty_layout.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E5E7EB;")
        ty_layout.addWidget(sep)

        self.font_size_widgets = {}
        fs_defaults = self.defaults.get("font_sizes", {})
        font_keys = [
            ("subject_header", "Subject Header"),
            ("adv_level",      "Adv. Level Label"),
            ("series",         "Series / Title"),
            ("paper_num",      "Paper Number"),
            ("instructions",   "Instructions"),
            ("question_num",   "Question No."),
            ("lecturer",       "Lecturer Name"),
            ("lecturer_qual",  "Qualification"),
            ("footer",         "Footer Text"),
        ]
        for key, label_text in font_keys:
            r = QHBoxLayout()
            r.setSpacing(8)
            el = QLabel(label_text)
            el.setStyleSheet("font-size: 12px; color: #374151; border: none;")
            r.addWidget(el, 2)
            sp = QSpinBox()
            sp.setRange(5, 100)
            sp.setValue(fs_defaults.get(key, 12))
            sp.setFixedHeight(28)
            sp.setStyleSheet(
                "QSpinBox { border: 1px solid #D1D5DB; border-radius: 4px;"
                " padding: 0 4px; font-size: 12px; min-height: 28px; }"
                "QSpinBox:focus { border-color: #f97316; }"
            )
            self.font_size_widgets[key] = sp
            r.addWidget(sp, 1)
            ty_layout.addLayout(r)

        # Tamil Font selector
        ty_layout.addSpacing(8)
        tamil_lbl = _field_label("Tamil Font")
        tamil_lbl.setStyleSheet("font-size: 11px; color: #9CA3AF; font-weight: 700; border: none;")
        ty_layout.addWidget(tamil_lbl)
        self.tamil_font_combo = QComboBox()
        self.tamil_font_combo.addItems(["Latha", "Nirmala UI", "Vijaya"])
        font_idx = self.tamil_font_combo.findText(self.defaults.get("tamil_font", "Latha"))
        if font_idx >= 0:
            self.tamil_font_combo.setCurrentIndex(font_idx)
        ty_layout.addWidget(self.tamil_font_combo)

        ty_layout.addStretch()
        row1.addWidget(ty_card, 0)
        cv.addLayout(row1)

        # ── Lecturer Details ──────────────────────────────────────────────────
        lec_card, lec_layout = _section_card("LECTURER DETAILS")
        lec_row = QHBoxLayout()
        lec_row.setSpacing(16)

        for label_text, attr_name, placeholder, default_key in [
            ("Lead Lecturer",    "lecturer_name_input",   "Dr. Sarah Jenkins",       "lecturer_name"),
            ("Department / Qualification", "lecturer_qual_input", "e.g. B.Sc Engineering", "lecturer_qualification"),
            ("Paper Number",     "paper_num_input",       "e.g. 1",                  "paper_number"),
        ]:
            col = QVBoxLayout()
            col.addWidget(_field_label(label_text))
            widget = QLineEdit(self.defaults.get(default_key, ""))
            widget.setPlaceholderText(placeholder)
            setattr(self, attr_name, widget)
            col.addWidget(widget)
            lec_row.addLayout(col)

        lec_layout.addLayout(lec_row)
        cv.addWidget(lec_card)

        # ── Page Formatting ───────────────────────────────────────────────────
        fmt_card, fmt_layout = _section_card("PAGE FORMATTING")
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(32)

        self.toggle_logo = ToggleSwitch(checked=bool(self.defaults.get("logo_path", "")))
        self.toggle_watermark = ToggleSwitch(checked=False)
        self.toggle_page_numbers = ToggleSwitch(checked=bool(self.defaults.get("show_page_numbers", True)))
        self.chk_reverse = ToggleSwitch(checked=True)

        for toggle, label_text in [
            (self.toggle_logo,         "Include Header Logo"),
            (self.toggle_watermark,    "Watermark Text"),
            (self.toggle_page_numbers, "Page Numbering"),
            (self.chk_reverse,         "Reverse Question Order"),
        ]:
            tg_col = QHBoxLayout()
            tg_col.setSpacing(10)
            tg_col.addWidget(toggle)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 13px; color: #374151; border: none;")
            tg_col.addWidget(lbl)
            toggles_row.addLayout(tg_col)

        toggles_row.addStretch()
        fmt_layout.addLayout(toggles_row)
        cv.addWidget(fmt_card)

        cv.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ── Bottom Action Bar ─────────────────────────────────────────────────
        action_bar = QWidget()
        action_bar.setStyleSheet(
            "background-color: #FFFFFF; border-top: 1px solid #E5E7EB;"
        )
        action_bar.setFixedHeight(64)
        ab_layout = QHBoxLayout(action_bar)
        ab_layout.setContentsMargins(32, 0, 32, 0)
        ab_layout.setSpacing(12)

        draft_note = QLabel("ℹ  All changes are automatically saved to draft.")
        draft_note.setStyleSheet("font-size: 12px; color: #6B7280; border: none;")
        ab_layout.addWidget(draft_note)
        ab_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #374151; border: 1px solid #D1D5DB;"
            " border-radius: 6px; font-weight: 600; }"
            "QPushButton:hover { background: #F3F4F6; }"
        )
        ab_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Configuration")
        apply_btn.setFixedSize(190, 40)
        apply_btn.setObjectName("applyBtn")
        apply_btn.clicked.connect(self.accept_config)
        apply_btn.setStyleSheet(
            "QPushButton { background-color: #f97316; color: #FFFFFF; border: none;"
            " border-radius: 6px; font-weight: 700; font-size: 13px; }"
            "QPushButton:hover { background-color: #ea6a0a; }"
            "QPushButton:pressed { background-color: #c2540a; }"
        )
        ab_layout.addWidget(apply_btn)

        root.addWidget(action_bar)

    # ── Subject management ────────────────────────────────────────────────────
    def populate_subjects(self):
        self.subject_combo.clear()
        subjects = ["PHYSICS"]
        if os.path.exists(SUBJECTS_CONFIG_PATH):
            try:
                with open(SUBJECTS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    subjects = list(data.keys())
            except Exception:
                pass
        self.subject_combo.addItems(subjects)
        idx = self.subject_combo.findText(self.defaults.get("subject", "PHYSICS"))
        if idx >= 0:
            self.subject_combo.setCurrentIndex(idx)

    def open_subject_manager(self):
        dlg = SubjectManagerDialog(self)
        dlg.subjects_updated.connect(self.populate_subjects)
        dlg.exec()

    # ── Accept / emit config ──────────────────────────────────────────────────
    def accept_config(self):
        footer_quote = self._normalize_quote(self.footer_quote_input.text())
        part_code = self.code3_input.text().strip() or self.defaults.get("part_code", "I") or "I"
        config = {
            "subject":              self.subject_combo.currentText() or "PHYSICS",
            "exam_series":          self.series_input.text().strip() or "Final Semester Assessment",
            "paper_number":         self.paper_num_input.text().strip() or "1",
            "duration":             self.duration_input.text().strip() or "120",
            "paper_code_1":         self.code1_input.text().strip() or "01",
            "paper_code_2":         self.code2_input.text().strip() or "T",
            "paper_code_3":         part_code,
            "part_code":            part_code,
            "lecturer_name":        self.lecturer_name_input.text().strip() or self.defaults.get("lecturer_name", ""),
            "lecturer_qualification": self.lecturer_qual_input.text().strip() or self.defaults.get("lecturer_qualification", ""),
            "logo_path":            self.defaults.get("logo_path", "logo.png"),
            "footer_quote":         footer_quote,
            "show_page_numbers":    self.toggle_page_numbers.isChecked(),
            "start_question_number": int(self.start_qnum_spin.value()),
            "layout":               self.defaults.get("layout", {}),
            "tamil_font":           self.tamil_font_combo.currentText(),
            "font_sizes":           {key: sb.value() for key, sb in self.font_size_widgets.items()},
        }
        self._save_defaults_to_config(footer_quote, part_code)
        self.config_accepted.emit(config)
        self.accept()

    # ── Compatibility shim: the old show_page_numbers_chk reference ───────────
    @property
    def show_page_numbers_chk(self):
        return self.toggle_page_numbers
