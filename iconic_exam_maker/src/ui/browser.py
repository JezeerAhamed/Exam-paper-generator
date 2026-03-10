import json
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class QuestionCard(QFrame):
    """Card showing thumbnail and question actions."""

    q_added = Signal(dict)  # Emits question metadata
    remove_requested = Signal(str, str)  # img_path, json_path
    selected = Signal(object)  # Emits QuestionCard
    preview_requested = Signal(object)  # Emits QuestionCard
    edit_requested = Signal(object)  # Emits QuestionCard

    def __init__(self, img_path, json_path):
        super().__init__()
        self.img_path = img_path
        self.json_path = json_path
        self._is_selected = False
        self.q_data = {"id": "Unknown", "img_path": self.img_path, "marks": 0, "topic": ""}
        self.init_ui()

    def _apply_card_style(self):
        border = "#3B82F6" if self._is_selected else "#E5E7EB"
        self.setStyleSheet(
            f"""
            QFrame#card {{
                background-color: #FFFFFF;
                border: 2px solid {border};
                border-radius: 14px;
            }}
            """
        )

    def set_selected(self, selected):
        self._is_selected = bool(selected)
        self._apply_card_style()

    def init_ui(self):
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(250, 285)
        self._apply_card_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self.img_label = QLabel()
        self.img_label.setFixedSize(228, 150)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background-color: #F8FAFC; border-radius: 8px; border: none;")

        if os.path.exists(self.img_path):
            pix = QPixmap(self.img_path)
            self.img_label.setPixmap(
                pix.scaled(220, 145, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

        layout.addWidget(self.img_label)

        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.q_data = json.load(f)
                    self.q_data["img_path"] = self.img_path
            except Exception:
                pass

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(3, 0, 3, 0)
        lbl = QLabel(self.q_data.get("id", self.q_data.get("label", "Unknown")))
        lbl.setStyleSheet("font-weight: 800; font-size: 13px; color: #2D3748; border: none;")
        info_layout.addWidget(lbl)
        info_layout.addStretch()

        marks = QLabel(f"{self.q_data.get('marks', 0)}M")
        marks.setStyleSheet("color: #38A169; font-weight: 800; font-size: 11px; border: none;")
        info_layout.addWidget(marks)
        layout.addLayout(info_layout)

        topic_text = self.q_data.get("topic", "") or "No topic"
        topic = QLabel(topic_text)
        topic.setStyleSheet("color: #7F8C8D; font-size: 11px; border: none;")
        topic.setWordWrap(True)
        topic.setFixedHeight(30)
        layout.addWidget(topic)

        self.btn_edit = QPushButton("Edit")
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setFixedHeight(30)
        self.btn_edit.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 0px; background-color: #FFFFFF; border: 1px solid #D6D6D6; color: #555555; border-radius: 4px; }"
            "QPushButton:hover { background-color: #F4F4F4; }"
        )
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self))
        row_2.addWidget(self.btn_edit)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setFixedHeight(30)
        self.btn_remove.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 0px; color: #DC2626; background-color: #FFFFFF; border: 1px solid #FECACA; border-radius: 4px; }"
            "QPushButton:hover { background-color: #FEF2F2; }"
        )
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.img_path, self.json_path))
        row_2.addWidget(self.btn_remove)
        layout.addLayout(row_2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self)
            self.preview_requested.emit(self)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class QuestionBankBrowser(QWidget):
    add_to_exam = Signal(dict)
    edit_requested = Signal(dict)

    def __init__(self, project_manager):
        super().__init__()
        self.pm = project_manager
        self.selected_card = None
        self.selected_payload = None
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(24)

        # Left Column (Controls + Grid)
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title = QLabel("Question Bank")
        title.setObjectName("header_title")
        header_layout.addWidget(title)
        header_layout.addStretch()
        left_layout.addLayout(header_layout)
        
        left_layout.addSpacing(10)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search by ID or topic...")
        self.search_bar.setFixedHeight(40)
        self.search_bar.textChanged.connect(self.refresh_grid)
        action_layout.addWidget(self.search_bar, 1)

        self.btn_add_all = QPushButton("Add All")
        self.btn_add_all.setObjectName("primary")
        self.btn_add_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_all.setFixedHeight(40)
        self.btn_add_all.setFixedWidth(100)
        self.btn_add_all.clicked.connect(self.add_all_questions)
        action_layout.addWidget(self.btn_add_all)

        self.btn_remove_all = QPushButton("Remove All")
        self.btn_remove_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_all.setFixedHeight(40)
        self.btn_remove_all.setFixedWidth(110)
        self.btn_remove_all.setStyleSheet("color: #DC2626; font-weight: 700; border: 1px solid #FECACA; background-color: #FFFFFF;")
        self.btn_remove_all.clicked.connect(self.remove_all_questions)
        action_layout.addWidget(self.btn_remove_all)
        left_layout.addLayout(action_layout)

        self.bank_stats_label = QLabel("Select a question to preview and edit.")
        self.bank_stats_label.setStyleSheet("color: #475569; font-size: 13px;")
        
        left_layout.addSpacing(15)
        left_layout.addWidget(self.bank_stats_label)
        left_layout.addSpacing(10)

        # Scroll area for grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: transparent;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll.setWidget(self.grid_container)
        left_layout.addWidget(self.scroll, 1)

        main_layout.addWidget(left_col, 1)

        # Right Column (Preview)
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("card")
        self.preview_frame.setFixedWidth(380)
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)

        self.preview_img = QLabel("No question selected")
        self.preview_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_img.setStyleSheet("background-color: #FFFFFF; border-radius: 8px;")
        self.preview_img.setMinimumHeight(200)
        self.preview_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview_img, 1)

        self.preview_title = QLabel("No selection")
        self.preview_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #0F172A; margin-top: 10px;")
        preview_layout.addWidget(self.preview_title)

        self.preview_meta = QLabel("")
        self.preview_meta.setStyleSheet("color: #64748B; font-size: 13px; line-height: 1.5;")
        self.preview_meta.setWordWrap(True)
        preview_layout.addWidget(self.preview_meta)

        self.preview_topic = QLabel("")
        self.preview_topic.setStyleSheet("color: #475569; font-size: 13px;")
        self.preview_topic.setWordWrap(True)
        preview_layout.addWidget(self.preview_topic)
        
        preview_layout.addSpacing(20)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_preview_large = QPushButton("Open Large Preview")
        self.btn_preview_large.setFixedHeight(36)
        self.btn_preview_large.clicked.connect(self.preview_selected_question)
        actions.addWidget(self.btn_preview_large, 1)

        self.btn_edit_selected = QPushButton("Edit in Review")
        self.btn_edit_selected.setObjectName("primary")
        self.btn_edit_selected.setFixedHeight(36)
        self.btn_edit_selected.clicked.connect(self.edit_selected_question)
        actions.addWidget(self.btn_edit_selected, 1)
        preview_layout.addLayout(actions)

        self.btn_add_selected = QPushButton("Add Selected")
        self.btn_add_selected.setObjectName("primary")
        self.btn_add_selected.setFixedHeight(40)
        self.btn_add_selected.clicked.connect(self.add_selected_question)
        preview_layout.addWidget(self.btn_add_selected)

        main_layout.addWidget(self.preview_frame)

        self._set_preview_enabled(False)

    def _set_preview_enabled(self, enabled):
        self.btn_preview_large.setEnabled(enabled)
        self.btn_edit_selected.setEnabled(enabled)
        self.btn_add_selected.setEnabled(enabled)

    def on_show(self):
        self.refresh_grid()

    def _build_payload(self, card):
        data = dict(card.q_data)
        data["img_path"] = card.img_path
        data["json_path"] = card.json_path
        data["id"] = data.get("id", data.get("label", "Unknown"))
        return data

    def _select_card(self, card):
        if self.selected_card and self.selected_card is not card:
            self.selected_card.set_selected(False)

        self.selected_card = card
        self.selected_card.set_selected(True)
        self.selected_payload = self._build_payload(card)
        self._update_preview()

    def _update_preview(self):
        data = self.selected_payload
        if not data:
            self.preview_img.setText("Select a question to preview")
            self.preview_img.setPixmap(QPixmap())
            self.preview_title.setText("No selection")
            self.preview_meta.setText("")
            self.preview_topic.setText("")
            self._set_preview_enabled(False)
            return

        img_path = data.get("img_path", "")
        pix = QPixmap(img_path) if img_path and os.path.exists(img_path) else QPixmap()
        if not pix.isNull():
            self.preview_img.setPixmap(
                pix.scaled(
                    self.preview_img.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview_img.setText("Preview unavailable")

        self.preview_title.setText(str(data.get("id", "Unknown")))
        self.preview_meta.setText(
            f"Marks: <span style='color: #333;'>{data.get('marks', 0)}</span><br>"
            f"Source: <span style='color: #333;'>{data.get('source_pdf', 'Unknown')}</span><br>"
            f"Page: <span style='color: #333;'>{data.get('page', '-')}</span>"
        )
        self.preview_meta.setTextFormat(Qt.TextFormat.RichText)
        self.preview_topic.setText(f"Topic: <span style='color: #333;'>{data.get('topic', 'N/A')}</span>")
        self.preview_topic.setTextFormat(Qt.TextFormat.RichText)
        if hasattr(self, "bank_stats_label"):
            self.bank_stats_label.setText(
                f"Selected {data.get('id', 'Question')}  •  Double-click card to open full preview."
            )
        self._set_preview_enabled(True)

    def _open_preview_dialog(self, img_path, title="Question Preview"):
        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "Preview", "Image file not found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(1100, 800)
        dlg_layout = QVBoxLayout(dlg)

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("background: #F8FAFC; border: 1px solid #CBD5E1;")
        pix = QPixmap(img_path)
        lbl.setPixmap(
            pix.scaled(1040, 740, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        dlg_layout.addWidget(lbl)
        dlg.exec()

    def preview_selected_question(self):
        if not self.selected_payload:
            return
        self._open_preview_dialog(
            self.selected_payload.get("img_path", ""),
            f"Preview - {self.selected_payload.get('id', 'Question')}",
        )

    def edit_selected_question(self):
        if not self.selected_payload:
            return
        self.edit_requested.emit(dict(self.selected_payload))

    def add_selected_question(self):
        if not self.selected_payload:
            return
        self.add_to_exam.emit(dict(self.selected_payload))

    def refresh_grid(self):
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.selected_card = None
        self.selected_payload = None
        self._update_preview()

        if not self.pm.current_project:
            return

        q_root = os.path.join(self.pm.current_project["path"], "questions")
        if not os.path.exists(q_root):
            return

        search_query = self.search_bar.text().strip().lower()
        col_count = 4
        row = 0
        col = 0

        pdf_dirs = [os.path.join(q_root, d) for d in os.listdir(q_root) if os.path.isdir(os.path.join(q_root, d))]

        all_questions = []
        for p_dir in pdf_dirs:
            for f in os.listdir(p_dir):
                if f.startswith("Q") and f.endswith(".json"):
                    json_path = os.path.join(p_dir, f)
                    img_path = json_path.replace(".json", ".png")
                    if os.path.exists(img_path):
                        all_questions.append((img_path, json_path))

        all_questions.sort(key=lambda x: os.path.getctime(x[0]), reverse=True)
        displayed = 0

        for img_p, json_p in all_questions:
            match = True
            if search_query:
                try:
                    with open(json_p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    qid = str(data.get("id", data.get("label", ""))).lower()
                    topic = str(data.get("topic", "")).lower()
                    if search_query not in qid and search_query not in topic:
                        match = False
                except Exception:
                    pass

            if not match:
                continue

            card = QuestionCard(img_p, json_p)
            card.q_added.connect(self.add_to_exam.emit)
            card.remove_requested.connect(self.remove_question)
            card.selected.connect(self._select_card)
            card.preview_requested.connect(
                lambda c: self._open_preview_dialog(c.img_path, f"Preview - {c.q_data.get('id', 'Question')}")
            )
            card.edit_requested.connect(lambda c: self.edit_requested.emit(self._build_payload(c)))
            self.grid_layout.addWidget(card, row, col)
            displayed += 1

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if hasattr(self, "bank_stats_label"):
            self.bank_stats_label.setText(
                f"Showing {displayed} of {len(all_questions)} questions. "
                "Select one to preview/edit."
            )

    def add_all_questions(self):
        count = self.grid_layout.count()
        if count == 0:
            return

        emitted = 0
        for i in range(count):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, QuestionCard):
                self.add_to_exam.emit(widget.q_data)
                emitted += 1
        QMessageBox.information(self, "Batch Add", f"Added {emitted} questions to the exam paper.")

    def remove_question(self, img_path, json_path):
        reply = QMessageBox.question(
            self,
            "Remove Question",
            "Delete this question from the question bank?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception as e:
            QMessageBox.warning(self, "Remove Failed", f"Could not remove question:\n{e}")
            return
        self.refresh_grid()

    def remove_all_questions(self):
        count = self.grid_layout.count()
        if count == 0:
            return
        reply = QMessageBox.question(
            self,
            "Remove All Displayed",
            f"Delete all {count} displayed questions from the question bank?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        removed = 0
        for i in range(count):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, QuestionCard):
                if os.path.exists(widget.json_path):
                    try:
                        os.remove(widget.json_path)
                    except Exception:
                        pass
                if os.path.exists(widget.img_path):
                    try:
                        os.remove(widget.img_path)
                    except Exception:
                        pass
                removed += 1
        self.refresh_grid()
        QMessageBox.information(self, "Remove Complete", f"Removed {removed} questions.")
