"""
HandoutConfigDialog  –  Iconic Academy
========================================
Dialog for configuring a unit-handout export.

Primary section: Unit Name (Line 1 + optional Line 2) with an adjustable
font-size spinner so the user has full control over the header headline.
"""

import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QFormLayout,
    QFrame, QSpinBox, QCheckBox,
)
from PySide6.QtCore import Qt, Signal


# ── Shared styles ─────────────────────────────────────────────────────────────

_INPUT_STYLE = (
    "QLineEdit, QComboBox, QSpinBox {"
    " min-height: 36px; border: 1px solid #D1D5DB; border-radius: 6px;"
    " padding: 0 10px; background: #FFFFFF; color: #111827; font-size: 13px; }"
    "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #f97316; }"
)

_UNIT_STYLE = (
    "QLineEdit {"
    " min-height: 46px; border: 2px solid #f97316; border-radius: 8px;"
    " padding: 0 14px; background: #FFF7ED; color: #111827;"
    " font-size: 15px; font-weight: 700; letter-spacing: 0.5px; }"
    "QLineEdit:focus { border-color: #ea580c; }"
)


def _card(title: str):
    """Returns (frame, inner_layout) for a section card."""
    frame = QFrame()
    frame.setStyleSheet(
        "QFrame { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; }"
    )
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 14, 20, 18)
    layout.setSpacing(10)
    lbl = QLabel(title)
    lbl.setStyleSheet(
        "font-size: 11px; font-weight: 700; color: #9CA3AF;"
        " letter-spacing: 1px; border: none; background: transparent;"
    )
    layout.addWidget(lbl)
    return frame, layout


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; border: none;")
    return l


# ── Dialog ────────────────────────────────────────────────────────────────────

class HandoutConfigDialog(QDialog):
    """
    Emits ``config_accepted(dict)`` when Generate is clicked.

    Config keys
    -----------
    unit_name         str   – line 1 of unit name (CHANGEABLE)
    unit_name_line2   str   – line 2 of unit name, empty = single line (CHANGEABLE)
    unit_font_size    int   – pt size for unit name text (CHANGEABLE)
    subject           str
    subject_level     str
    institute_name    str
    lecturer_name     str
    lecturer_qual     str
    """

    config_accepted = Signal(dict)
    _last: dict = {}   # class-level memory between calls

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Handout Configuration")
        self.setMinimumWidth(530)
        self.setStyleSheet("QDialog { background: #F9FAFB; }")
        self._build_ui()
        self._load_defaults()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)

        # Title
        ttl = QLabel("Unit Handout  –  Header Setup")
        ttl.setStyleSheet("font-size: 17px; font-weight: 700; color: #111827;")
        root.addWidget(ttl)

        sub = QLabel("The Unit Name appears as the large headline text on the metallic banner.")
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 12px; color: #6B7280;")
        root.addWidget(sub)

        # ── UNIT NAME card ────────────────────────────────────────────────────
        u_card, u_inner = _card("UNIT NAME  (main changeable text)")

        # Line 1
        u_inner.addWidget(_lbl("Line 1:"))
        self.txt_unit1 = QLineEdit()
        self.txt_unit1.setPlaceholderText("e.g.  MATTER AND RADIATION")
        self.txt_unit1.setStyleSheet(_UNIT_STYLE)
        u_inner.addWidget(self.txt_unit1)

        # Line 2 (optional)
        u_inner.addWidget(_lbl("Line 2  (optional – leave blank for single line):"))
        self.txt_unit2 = QLineEdit()
        self.txt_unit2.setPlaceholderText("e.g.  RADIATION  (or leave empty)")
        self.txt_unit2.setStyleSheet(_UNIT_STYLE)
        u_inner.addWidget(self.txt_unit2)

        # Font size row
        size_row = QHBoxLayout()
        size_row.setSpacing(10)
        size_row.addWidget(_lbl("Unit Name Font Size (pt):"))
        self.spin_unit_size = QSpinBox()
        self.spin_unit_size.setRange(18, 90)
        self.spin_unit_size.setValue(56)
        self.spin_unit_size.setSuffix(" pt")
        self.spin_unit_size.setFixedWidth(100)
        self.spin_unit_size.setStyleSheet(_INPUT_STYLE)
        self.spin_unit_size.setToolTip(
            "Font size for the unit name.\n"
            "Larger = more prominent. Will auto-shrink if text is too wide."
        )
        size_row.addWidget(self.spin_unit_size)
        size_row.addStretch()
        u_inner.addLayout(size_row)

        root.addWidget(u_card)

        # ── SUBJECT card ──────────────────────────────────────────────────────
        s_card, s_inner = _card("SUBJECT")
        s_form = QFormLayout()
        s_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        s_form.setSpacing(10)

        self.cmb_subject = QComboBox()
        self.cmb_subject.addItems(["PHYSICS", "CHEMISTRY", "BIOLOGY",
                                   "COMBINED MATHS", "OTHER"])
        self.cmb_subject.setEditable(True)
        self.cmb_subject.setStyleSheet(_INPUT_STYLE)
        s_form.addRow(_lbl("Subject:"), self.cmb_subject)

        self.txt_level = QLineEdit("Advanced Level")
        self.txt_level.setStyleSheet(_INPUT_STYLE)
        s_form.addRow(_lbl("Level:"), self.txt_level)

        s_inner.addLayout(s_form)
        root.addWidget(s_card)

        # ── INSTITUTE & LECTURER card ─────────────────────────────────────────
        i_card, i_inner = _card("INSTITUTE & LECTURER")
        i_form = QFormLayout()
        i_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        i_form.setSpacing(10)

        self.txt_institute = QLineEdit("ICONIC ACADEMY")
        self.txt_institute.setStyleSheet(_INPUT_STYLE)
        i_form.addRow(_lbl("Institute:"), self.txt_institute)

        self.txt_lecturer = QLineEdit()
        self.txt_lecturer.setStyleSheet(_INPUT_STYLE)
        i_form.addRow(_lbl("Lecturer:"), self.txt_lecturer)

        self.txt_qual = QLineEdit()
        self.txt_qual.setStyleSheet(_INPUT_STYLE)
        i_form.addRow(_lbl("Qualification:"), self.txt_qual)

        i_inner.addLayout(i_form)
        root.addWidget(i_card)

        # ── HEADER STYLE toggle ───────────────────────────────────────────────
        self.chk_white_bg = QCheckBox("White background  (remove metallic effect)")
        self.chk_white_bg.setStyleSheet(
            "QCheckBox { font-size: 13px; color: #374151; }"
            "QCheckBox::indicator { width: 18px; height: 18px; }"
        )
        root.addWidget(self.chk_white_bg)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setMinimumWidth(90)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#F3F4F6; border:1px solid #D1D5DB;"
            " border-radius:6px; font-size:13px; }"
            "QPushButton:hover { background:#E5E7EB; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_gen = QPushButton("Generate Handout PDF")
        btn_gen.setFixedHeight(40)
        btn_gen.setMinimumWidth(190)
        btn_gen.setStyleSheet(
            "QPushButton { background:#f97316; color:white; border:none;"
            " border-radius:6px; font-size:13px; font-weight:700; }"
            "QPushButton:hover { background:#ea580c; }"
            "QPushButton:pressed { background:#c2410c; }"
        )
        btn_gen.clicked.connect(self._on_generate)
        btn_row.addWidget(btn_gen)

        root.addLayout(btn_row)

    # ── Load defaults ─────────────────────────────────────────────────────────

    def _load_defaults(self):
        cfg_path = os.path.join("config", "config.json")
        inst = {}
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    inst = json.load(f).get("institute", {})
        except Exception:
            pass

        last = HandoutConfigDialog._last

        lecturer = last.get("lecturer_name") or inst.get("lecturer_name", "M.M. JEZEER AHAMED")
        qual     = last.get("lecturer_qual") or inst.get("lecturer_qualification", "B.Sc (Engineering)")

        self.txt_lecturer.setText(lecturer)
        if "white_background" in last:
            self.chk_white_bg.setChecked(bool(last["white_background"]))
        self.txt_qual.setText(qual)

        # Restore last-used values
        if last.get("unit_name"):
            self.txt_unit1.setText(last["unit_name"])
        if last.get("unit_name_line2"):
            self.txt_unit2.setText(last["unit_name_line2"])
        if last.get("unit_font_size"):
            self.spin_unit_size.setValue(int(last["unit_font_size"]))
        if last.get("subject"):
            idx = self.cmb_subject.findText(last["subject"])
            if idx >= 0:
                self.cmb_subject.setCurrentIndex(idx)
            else:
                self.cmb_subject.setEditText(last["subject"])
        if last.get("subject_level"):
            self.txt_level.setText(last["subject_level"])
        if last.get("institute_name"):
            self.txt_institute.setText(last["institute_name"])

    # ── Generate ──────────────────────────────────────────────────────────────

    def _on_generate(self):
        config = {
            "unit_name"        : self.txt_unit1.text().strip().upper() or "UNIT NAME",
            "unit_name_line2"  : self.txt_unit2.text().strip().upper(),
            "unit_font_size"   : self.spin_unit_size.value(),
            "subject"          : self.cmb_subject.currentText().strip().upper(),
            "subject_level"    : self.txt_level.text().strip() or "Advanced Level",
            "institute_name"   : self.txt_institute.text().strip() or "ICONIC ACADEMY",
            "lecturer_name"    : self.txt_lecturer.text().strip(),
            "lecturer_qual"    : self.txt_qual.text().strip(),
            "white_background" : self.chk_white_bg.isChecked(),
        }
        HandoutConfigDialog._last = dict(config)
        self.config_accepted.emit(config)
        self.accept()
