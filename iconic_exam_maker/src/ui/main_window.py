from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QGraphicsOpacityEffect, QMessageBox, QApplication)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon
import os
from src.backend.project import ProjectManager
from src.ui.dashboard import Dashboard
from src.ui.importer import Importer
from src.ui.editor import Editor
from src.ui.browser import QuestionBankBrowser
from src.ui.builder import ExamBuilder
from src.ui.advanced_settings_dialog import AdvancedSettingsDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Iconic Exam Maker")
        self.resize(1280, 800)
        
        # Backend
        self.pm = ProjectManager()
        
        # Central Widget
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralwidget")
        self.central_widget.setObjectName("centralwidget")
        self.setCentralWidget(self.central_widget)
        
        # Main Layout (Sidebar + Content)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Sidebar
        self.setup_sidebar()
        
        # Content Area
        self.content_stack = QStackedWidget()
        self.main_layout.addWidget(self.content_stack)
        
        # --- SCREENS ---
        # 0: Dashboard
        self.dashboard = Dashboard(self.pm)
        self.dashboard.project_opened.connect(self.on_project_opened)
        self.content_stack.addWidget(self.dashboard)
        
        # 1: Importer
        self.importer = Importer(self.pm)
        self.importer.processing_requested.connect(self.start_cropping)
        self.content_stack.addWidget(self.importer)
        
        # 2: Question Bank (Browser)
        self.browser = QuestionBankBrowser(self.pm)
        self.content_stack.addWidget(self.browser)
        
        # 3: Editor (Detection Preview)
        self.editor = Editor(self.pm)
        self.content_stack.addWidget(self.editor)
        
        # 4: Exam Builder
        self.builder = ExamBuilder(self.pm)
        self.content_stack.addWidget(self.builder)
        
        # --- CONNECTIONS ---
        self.browser.add_to_exam.connect(self.builder.add_question)
        self.browser.edit_requested.connect(self.open_question_for_edit)
        
        # Set Dashboard as default
        self.content_stack.setCurrentWidget(self.dashboard)
        self._attach_button_pop(self)

    def setup_sidebar(self):
        # ... (Sidebar code remains same) ...
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 20, 0, 20)
        self.sidebar_layout.setSpacing(10)
        
        # App Logo / Title
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(16, 10, 16, 0)
        top_layout.setSpacing(10)
        
        title = QLabel("ICONIC\nACADEMY")
        title.setObjectName("app_title")
        
        atom_icon = QLabel("⚛️")
        atom_icon.setStyleSheet("font-size: 28px; color: #789BCC;")
        
        top_layout.addWidget(title)
        top_layout.addWidget(atom_icon)
        top_layout.addStretch()
        
        self.sidebar_layout.addWidget(top_row)
        self.sidebar_layout.addSpacing(20)
        
        # Navigation Buttons
        self.nav_btns = {}
        self.add_nav_btn("Dashboard", 0, True, icon_text="⏱️")
        self.add_nav_btn("Import Projects", 1, enabled=False, icon_text="📁")
        self.add_nav_btn("Question Bank", 2, enabled=False, icon_text="📋") 
        self.add_nav_btn("Review & Edit", 3, enabled=False, icon_text="📝") 
        self.add_nav_btn("Paper Builder", 4, enabled=False, icon_text="🛠️") 
        self.add_nav_btn("Settings", 5, icon_text="⚙️")
        
        self.sidebar_layout.addStretch()
        
        # Validated User Info
        version = self._load_version()
        user_info = QLabel(f"v{version} | Pro")
        user_info.setObjectName("version_label")
        user_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(user_info)
        
        self.main_layout.addWidget(self.sidebar)

    def add_nav_btn(self, text, index, active=False, enabled=True, icon_text=""):
        display_text = f"  {icon_text}    {text}" if icon_text else text
        btn = QPushButton(display_text)
        btn.setProperty("nav", "true")
        btn.setCheckable(True)
        if active: btn.setChecked(True)
        btn.setEnabled(enabled)
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Navigation Click
        btn.clicked.connect(lambda: self.switch_screen(index, btn))
        
        self.nav_btns[text] = btn
        self.sidebar_layout.addWidget(btn)

    def _load_version(self):
        version_path = os.path.join("VERSION")
        if os.path.exists(version_path):
            try:
                with open(version_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return "1.0.0"

    def switch_screen(self, index, btn_sender):
        # Settings dialog (separate popup)
        if index == 5:
            dlg = AdvancedSettingsDialog(self)
            dlg.exec()
            # Keep current selection
            if btn_sender:
                btn_sender.setChecked(False)
            return

        # Update stack
        if index < self.content_stack.count():
            self.content_stack.setCurrentIndex(index)
            # Call on_show if exists
            widget = self.content_stack.currentWidget()
            if hasattr(widget, 'on_show'):
                widget.on_show()
            self._fade_in(widget)
            self._attach_button_pop(widget)
            
        # Update buttons state
        for btn in self.nav_btns.values():
            btn.setChecked(False)
        if btn_sender:
            btn_sender.setChecked(True)

    def on_project_opened(self, project_data):
        print(f"Project Opened: {project_data['name']}")
        
        # Enable tabs
        self.nav_btns["Import Projects"].setEnabled(True)
        self.nav_btns["Question Bank"].setEnabled(True)
        self.nav_btns["Review & Edit"].setEnabled(True)
        self.nav_btns["Paper Builder"].setEnabled(True)
        self.setWindowTitle(f"Iconic Exam Maker - {project_data['name']}")
        
        # Auto-switch to Import Screen
        self.switch_screen(1, self.nav_btns["Import Projects"])

    def _fade_in(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        widget._fade_anim = anim

    def _attach_button_pop(self, root):
        for btn in root.findChildren(QPushButton):
            if btn.property("_pop_attached"):
                continue
            btn.setProperty("_pop_attached", True)
            btn.pressed.connect(lambda b=btn: self._pop_button(b, 0.96))
            btn.released.connect(lambda b=btn: self._pop_button(b, 1.0))

    def _pop_button(self, btn, scale):
        base = btn.property("_base_geo")
        if base is None:
            base = btn.geometry()
            btn.setProperty("_base_geo", base)
        rect = btn.geometry()
        new_w = max(1, int(base.width() * scale))
        new_h = max(1, int(base.height() * scale))
        new_rect = rect
        new_rect.setWidth(new_w)
        new_rect.setHeight(new_h)
        new_rect.moveCenter(base.center())

        # Animation disabled for Acrobat Flat aesthetic
        # anim = QPropertyAnimation(btn, b"geometry", btn)
        # anim.setDuration(90)
        # anim.setStartValue(rect)
        # anim.setEndValue(new_rect)
        # anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # anim.start()
        # btn._pop_anim = anim
        pass

    def start_cropping(self, payload):
        if isinstance(payload, dict):
            file_paths = payload.get("file_paths", [])
            auto_crop_enabled = bool(payload.get("auto_crop_enabled", False))
            page_limit = payload.get("page_limit")
        else:
            file_paths = payload
            auto_crop_enabled = False
            page_limit = None

        if not file_paths:
            return

        self._activate_editor_screen()
        QApplication.processEvents()

        self.editor.start_processing(
            file_paths,
            auto_crop=auto_crop_enabled,
            page_limit=page_limit,
        )

    def _activate_editor_screen(self):
        """Show editor screen without triggering resume prompts via on_show."""
        self.content_stack.setCurrentWidget(self.editor)
        self._fade_in(self.editor)
        self._attach_button_pop(self.editor)
        for btn in self.nav_btns.values():
            btn.setChecked(False)
        self.nav_btns["Review & Edit"].setEnabled(True)
        self.nav_btns["Review & Edit"].setChecked(True)
        self.nav_btns["Import Projects"].setChecked(False)

    def _resolve_source_pdf_path(self, q_data):
        """Resolve source PDF path from question metadata."""
        raw_source = str(q_data.get("source_pdf_path", "") or "").strip()
        if raw_source and os.path.exists(raw_source):
            return raw_source

        source_pdf = str(q_data.get("source_pdf", "") or "").strip()
        if source_pdf and os.path.isabs(source_pdf) and os.path.exists(source_pdf):
            return source_pdf

        if not self.pm.current_project:
            return None

        project_root = self.pm.current_project["path"]
        candidates = []
        if source_pdf:
            base_name = os.path.basename(source_pdf)
            candidates.append(os.path.join(project_root, "pdfs", base_name))
            candidates.append(os.path.join(project_root, base_name))

        for path in candidates:
            if path and os.path.exists(path):
                return path

        if source_pdf:
            target = os.path.basename(source_pdf).lower()
            for root, _dirs, files in os.walk(project_root):
                for f in files:
                    if f.lower() == target:
                        return os.path.join(root, f)
        return None

    def open_question_for_edit(self, q_data):
        """Open source PDF page in editor so user can manually crop missed questions."""
        pdf_path = self._resolve_source_pdf_path(q_data)
        if not pdf_path:
            QMessageBox.warning(
                self,
                "Source PDF Not Found",
                "Could not locate the source PDF for this question.\n"
                "Please re-import/open the original PDF and crop manually.",
            )
            return

        try:
            page = max(1, int(q_data.get("page", 1)))
        except Exception:
            page = 1

        self._activate_editor_screen()
        self.editor.open_pdf_at_page(pdf_path, page - 1)

        if hasattr(self.editor, "edit_topic"):
            self.editor.edit_topic.setText(str(q_data.get("topic", "") or ""))
        if hasattr(self.editor, "edit_marks"):
            try:
                self.editor.edit_marks.setValue(int(q_data.get("marks", 0) or 0))
            except Exception:
                self.editor.edit_marks.setValue(0)

        qid = q_data.get("id", "question")
        self.editor.lbl_info.setText(
            f"Editing source page for {qid}. Draw new crop area(s) for missed questions."
        )

