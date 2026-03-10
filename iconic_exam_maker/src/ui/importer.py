import os
import fitz
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QListWidget, QListWidgetItem, 
                               QFileDialog, QFrame, QProgressBar, QSpinBox, QCheckBox)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QDragEnterEvent, QDropEvent

class FileCard(QFrame):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.filename = os.path.basename(path)
        self.status = "Pending"
        
        # Get page count (fast)
        try:
            doc = fitz.open(path)
            self.page_count = len(doc)
            doc.close()
        except:
            self.page_count = 0
            self.status = "Error"

        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(80)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ECF0F1;
                border-radius: 6px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Icon
        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 24px; border: none;")
        layout.addWidget(icon_label)
        
        # Details
        info_layout = QVBoxLayout()
        name = QLabel(self.filename)
        name.setStyleSheet("font-weight: bold; font-size: 14px; border: none;")
        meta = QLabel(f"{self.page_count} Pages • {self.getStatusMsg()}")
        meta.setStyleSheet("color: #7F8C8D; font-size: 12px; border: none;")
        
        info_layout.addWidget(name)
        info_layout.addWidget(meta)
        layout.addLayout(info_layout)
        
        layout.addStretch()
        
        # Status Badge
        self.badge = QLabel(self.status)
        self.update_badge_style()
        layout.addWidget(self.badge)
        
        # Remove Btn
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(30, 30)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                color: #E74C3C; border: none; font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FDEDEC; border-radius: 15px;
            }
        """)
        layout.addWidget(del_btn)

    def getStatusMsg(self):
        return "Ready to process" if self.status == "Pending" else self.status
        
    def update_badge_style(self):
        color = "#F1C40F" # Pending Yellow
        if self.status == "Processed": color = "#2ECC71"
        elif self.status == "Error": color = "#E74C3C"
        
        self.badge.setStyleSheet(f"""
            padding: 5px 10px;
            background-color: {color}20; /* 20% opacity */
            color: {color};
            border: 1px solid {color};
            border-radius: 12px;
            font-weight: bold;
            font-size: 11px;
        """)

class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #BDC3C7;
                border-radius: 12px;
                background-color: #FDFFE6; /* Slight tint */
            }
            QFrame:hover {
                border-color: #1ABC9C;
                background-color: #E8F8F5;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        label = QLabel("Drag & Drop PDF Files Here\nor click to browse")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #7F8C8D; font-size: 16px; border: none;")
        layout.addWidget(label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith('.pdf')]
        if paths:
            self.files_dropped.emit(paths)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            paths, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
            if paths:
                self.files_dropped.emit(paths)

class Importer(QWidget):
    processing_requested = Signal(object) # Emits processing payload

    def __init__(self, project_manager):
        super().__init__()
        self.pm = project_manager
        self.file_paths = []
        self.page_counts = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Crop Your PDF")
        header.setObjectName("header_title")
        layout.addWidget(header)
        
        # Description
        sub = QLabel("Upload PDF(s), choose page limit, and auto-crop all questions up to that page.")
        sub.setStyleSheet("font-size: 15px; color: #718096; margin-bottom: 20px;")
        layout.addWidget(sub)
        
        # Drop Zone
        self.drop_zone = DropZone()
        self.drop_zone.setFixedHeight(200)
        self.drop_zone.files_dropped.connect(self.add_files)
        layout.addWidget(self.drop_zone)
        
        # File List (Condensed)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background-color: transparent; border: none;")
        self.list_widget.setFixedHeight(150)
        layout.addWidget(self.list_widget)

        # Auto Crop Controls
        options_row = QHBoxLayout()
        options_row.setSpacing(10)

        self.chk_auto_crop = QCheckBox("Auto crop questions with AI")
        self.chk_auto_crop.setChecked(True)
        options_row.addWidget(self.chk_auto_crop)

        page_lbl = QLabel("Up to page:")
        page_lbl.setStyleSheet("font-weight: 600; color: #4A5568;")
        options_row.addWidget(page_lbl)

        self.spin_page_limit = QSpinBox()
        self.spin_page_limit.setRange(1, 1)
        self.spin_page_limit.setValue(1)
        self.spin_page_limit.setFixedWidth(90)
        options_row.addWidget(self.spin_page_limit)

        options_row.addStretch()
        layout.addLayout(options_row)
        
        # Footer Actions
        action_layout = QHBoxLayout()
        self.lbl_count = QLabel("No file selected")
        self.lbl_count.setStyleSheet("font-weight: 600; color: #4A5568;")
        action_layout.addWidget(self.lbl_count)
        
        action_layout.addStretch()
        
        self.btn_process = QPushButton("Start Cropping ➔")
        self.btn_process.setObjectName("primary")
        self.btn_process.setFixedSize(240, 50)
        self.btn_process.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_process.clicked.connect(self.start_processing)
        self.btn_process.setEnabled(False)
        action_layout.addWidget(self.btn_process)
        
        layout.addLayout(action_layout)

    def add_files(self, paths):
        for path in paths:
            if path not in self.file_paths:
                self.file_paths.append(path)
                page_count = 0
                try:
                    doc = fitz.open(path)
                    page_count = len(doc)
                    doc.close()
                except Exception:
                    page_count = 0
                self.page_counts[path] = page_count

                item = QListWidgetItem(self.list_widget)
                item.setText(os.path.basename(path))
                item.setIcon(QIcon.fromTheme("document-pdf"))
        
        self.update_count()

    def update_count(self):
        count = len(self.file_paths)
        self.lbl_count.setText(f"{count} file(s) ready")
        self.btn_process.setEnabled(count > 0)
        max_pages = max([self.page_counts.get(p, 0) for p in self.file_paths] + [1])
        self.spin_page_limit.setRange(1, max_pages)
        self.spin_page_limit.setValue(min(self.spin_page_limit.value(), max_pages))

    def start_processing(self):
        if not self.file_paths:
            return
        payload = {
            "file_paths": list(self.file_paths),
            "auto_crop_enabled": bool(self.chk_auto_crop.isChecked()),
            "page_limit": int(self.spin_page_limit.value()),
        }
        # MainWindow will switch to Editor and run crop flow.
        self.processing_requested.emit(payload)
