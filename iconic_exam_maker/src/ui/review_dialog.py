import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QFrame, QScrollArea)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut
from PIL import Image


class ReviewDialog(QDialog):
    """
    Human-in-the-Loop Review System.
    Review cropped images sequentially: Accept (Keep) or Reject (Delete).
    """
    
    review_completed = Signal(dict)  # Emits summary: {kept: int, rejected: int}
    
    def __init__(self, image_files, parent=None):
        super().__init__(parent)
        self.image_files = image_files  # List of file paths
        self.index = 0
        self.total = len(image_files)
        self.rejected_count = 0
        self.rejected_files = []
        
        self.setWindowTitle(f"Review Mode - {self.total} Questions")
        self.resize(900, 700)
        self.setModal(True)
        
        self.init_ui()
        self.setup_shortcuts()
        self.show_image()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Instructions Header
        header = QLabel("✅ KEEP: Enter/Space | ❌ REJECT: Delete/X | ⬅ BACK: Left Arrow")
        header.setStyleSheet("""
            background-color: #e1f5fe;
            color: #01579b;
            font-size: 14px;
            font-weight: bold;
            padding: 15px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Status Label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("padding: 10px; font-size: 13px; color: #424242;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Image Container with Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #f5f5f5; border: none;")
        
        self.img_frame = QFrame()
        self.img_frame.setStyleSheet("background-color: white;")
        frame_layout = QVBoxLayout(self.img_frame)
        frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("padding: 20px;")
        frame_layout.addWidget(self.img_label)
        
        scroll.setWidget(self.img_frame)
        layout.addWidget(scroll, 1)
        
        # Button Frame
        btn_frame = QFrame()
        btn_frame.setStyleSheet("background-color: white; padding: 15px;")
        btn_layout = QHBoxLayout(btn_frame)
        
        btn_layout.addStretch()
        
        # Reject Button
        self.btn_reject = QPushButton("❌ REJECT (Del)")
        self.btn_reject.setFixedSize(180, 50)
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #ffcdd2;
                color: #c62828;
                border: 2px solid #ef5350;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ef9a9a;
            }
        """)
        self.btn_reject.clicked.connect(self.reject_current)
        btn_layout.addWidget(self.btn_reject)
        
        btn_layout.addSpacing(30)
        
        # Keep Button
        self.btn_keep = QPushButton("✅ KEEP (Enter)")
        self.btn_keep.setFixedSize(180, 50)
        self.btn_keep.setStyleSheet("""
            QPushButton {
                background-color: #c8e6c9;
                color: #2e7d32;
                border: 2px solid #66bb6a;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a5d6a7;
            }
        """)
        self.btn_keep.clicked.connect(self.keep_current)
        btn_layout.addWidget(self.btn_keep)
        
        btn_layout.addStretch()
        
        layout.addWidget(btn_frame)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Keep shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.keep_current)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.keep_current)
        
        # Reject shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.reject_current)
        QShortcut(QKeySequence(Qt.Key.Key_X), self, self.reject_current)
        
        # Back shortcut
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.prev_image)
    
    def show_image(self):
        """Display current image"""
        if 0 <= self.index < self.total:
            img_path = self.image_files[self.index]
            
            # Update status
            filename = os.path.basename(img_path)
            self.status_label.setText(
                f"Question {self.index + 1} of {self.total} | {filename}"
            )
            
            # Load and display image
            try:
                pixmap = QPixmap(img_path)
                
                # Scale to fit (max 800x550)
                if pixmap.width() > 800 or pixmap.height() > 550:
                    pixmap = pixmap.scaled(
                        800, 550,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                
                self.img_label.setPixmap(pixmap)
            except Exception as e:
                print(f"Error loading {img_path}: {e}")
                self.keep_current()  # Skip bad files
        else:
            self.finish_review()
    
    def keep_current(self):
        """Keep current image and move to next"""
        self.index += 1
        self.show_image()
    
    def reject_current(self):
        """Reject current image (move to _rejected folder)"""
        file_path = self.image_files[self.index]
        
        # Create rejected directory
        parent_dir = os.path.dirname(os.path.dirname(file_path))
        rejected_dir = os.path.join(parent_dir, "_rejected")
        os.makedirs(rejected_dir, exist_ok=True)
        
        dest_path = os.path.join(rejected_dir, os.path.basename(file_path))
        
        try:
            # Handle duplicate names
            if os.path.exists(dest_path):
                from datetime import datetime
                base, ext = os.path.splitext(dest_path)
                dest_path = f"{base}_{int(datetime.now().timestamp())}{ext}"
            
            os.rename(file_path, dest_path)
            self.rejected_files.append(file_path)
            self.image_files.pop(self.index)
            self.total -= 1
            self.rejected_count += 1
            
            # Don't increment index, next image slides into this slot
            self.show_image()
        except Exception as e:
            print(f"Error rejecting file: {e}")
            self.keep_current()  # Skip on error
    
    def prev_image(self):
        """Go back to previous image"""
        if self.index > 0:
            self.index -= 1
            self.show_image()
    
    def finish_review(self):
        """Complete review and emit summary"""
        summary = {
            "kept": self.total,
            "rejected": self.rejected_count,
            "rejected_files": self.rejected_files
        }
        self.review_completed.emit(summary)
        self.accept()
