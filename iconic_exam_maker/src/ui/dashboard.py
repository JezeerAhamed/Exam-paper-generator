from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame, QFileDialog,
                               QInputDialog, QMessageBox, QSizePolicy, QSpacerItem)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPainterPath
from datetime import datetime
import os


# ─────────────────────────────────────────────────────────────────────────────
# Helper: section title label
# ─────────────────────────────────────────────────────────────────────────────
def _section_title(icon: str, text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet("font-size: 18px; border: none; background: transparent;")
    row.addWidget(icon_lbl)
    txt = QLabel(text)
    txt.setStyleSheet(
        "font-size: 16px; font-weight: 700; color: #1C1C1E;"
        " border: none; background: transparent;"
    )
    row.addWidget(txt)
    row.addStretch()
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Quick Action Card
# ─────────────────────────────────────────────────────────────────────────────
class ActionCard(QFrame):
    clicked = Signal()

    def __init__(self, icon: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("action_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame#action_card { background: #FFFFFF; border: 1px solid #E5E7EB;"
            " border-radius: 12px; }"
            "QFrame#action_card:hover { border-color: #f97316; background: #FFFAF7; }"
        )
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(16)

        # Icon badge
        icon_badge = QLabel(icon)
        icon_badge.setFixedSize(44, 44)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setStyleSheet(
            "background-color: #FFF0E6; border-radius: 10px;"
            " font-size: 20px; border: none;"
        )
        row.addWidget(icon_badge)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #111827; border: none;"
        )
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setStyleSheet(
            "font-size: 12px; color: #6B7280; border: none;"
        )
        text_col.addWidget(title_lbl)
        text_col.addWidget(subtitle_lbl)
        row.addLayout(text_col, 1)

        # Chevron
        arrow = QLabel("›")
        arrow.setStyleSheet("font-size: 22px; color: #D1D5DB; border: none;")
        row.addWidget(arrow)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ─────────────────────────────────────────────────────────────────────────────
# Recent Project Row
# ─────────────────────────────────────────────────────────────────────────────
def _time_ago(ts) -> str:
    """Convert a timestamp to human-readable 'X ago'."""
    try:
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
        elif isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        else:
            return "Recently"
        diff = datetime.now() - dt
        if diff.days >= 7:
            return dt.strftime("%b %d")
        elif diff.days >= 2:
            return f"{diff.days} days ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"
    except Exception:
        return "Recently"


class RecentProjectRow(QFrame):
    open_requested = Signal(str)

    def __init__(self, project_data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("recent_row")
        self.setStyleSheet(
            "QFrame#recent_row { background: transparent; border: none;"
            " border-bottom: 1px solid #F3F4F6; }"
        )
        self.setFixedHeight(64)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)

        # Doc icon
        doc_icon = QLabel("📄")
        doc_icon.setFixedSize(36, 36)
        doc_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        doc_icon.setStyleSheet(
            "background-color: #FFF0E6; border-radius: 8px;"
            " font-size: 16px; border: none; color: #f97316;"
        )
        row.addWidget(doc_icon)

        # Name
        name_lbl = QLabel(project_data.get("name", "Untitled Project"))
        name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #111827; border: none;"
        )
        row.addWidget(name_lbl, 2)

        # Time
        ts = project_data.get("timestamp") or project_data.get("last_modified")
        time_lbl = QLabel(_time_ago(ts))
        time_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF; border: none;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(time_lbl, 1)

        # Open button
        open_btn = QPushButton("Open")
        open_btn.setFixedSize(60, 32)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(
            "QPushButton { background-color: #f97316; color: #FFF; border: none;"
            " border-radius: 6px; font-size: 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: #ea6a0a; }"
        )
        open_btn.clicked.connect(lambda: self.open_requested.emit(project_data.get("path", "")))
        row.addWidget(open_btn)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Widget
# ─────────────────────────────────────────────────────────────────────────────
class Dashboard(QWidget):
    project_opened = Signal(object)

    def __init__(self, project_manager):
        super().__init__()
        self.pm = project_manager
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #F3F4F6;")

        # Outer scroll
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        page = QWidget()
        page.setStyleSheet("background: transparent;")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ── Top App Bar ──────────────────────────────────────────────────────
        app_bar = QWidget()
        app_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E5E7EB;")
        app_bar.setFixedHeight(64)
        ab_row = QHBoxLayout(app_bar)
        ab_row.setContentsMargins(24, 0, 24, 0)
        ab_row.setSpacing(12)

        # Avatar circle
        avatar = QLabel("🎓")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background-color: #f97316; border-radius: 20px;"
            " font-size: 18px; border: none;"
        )
        ab_row.addWidget(avatar)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        wb = QLabel("Welcome Back")
        wb.setStyleSheet("font-size: 15px; font-weight: 700; color: #111827; border: none;")
        sub = QLabel("Iconic Academy Dashboard")
        sub.setStyleSheet("font-size: 11px; color: #9CA3AF; border: none;")
        title_col.addWidget(wb)
        title_col.addWidget(sub)
        ab_row.addLayout(title_col)
        ab_row.addStretch()

        bell_btn = QPushButton("🔔")
        bell_btn.setFixedSize(40, 40)
        bell_btn.setStyleSheet(
            "QPushButton { background: #F9FAFB; border: 1px solid #E5E7EB;"
            " border-radius: 10px; font-size: 16px; }"
            "QPushButton:hover { background: #F3F4F6; }"
        )
        ab_row.addWidget(bell_btn)
        v.addWidget(app_bar)

        # ── Content ──────────────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(24, 24, 24, 24)
        cv.setSpacing(24)

        # ── Hero Banner ──────────────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet(
            "QFrame { background-color: #1C2333; border-radius: 16px; border: none; }"
        )
        hero.setFixedHeight(180)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(10)

        hero_title = QLabel("Build beautiful exam papers\nwith clarity and speed")
        hero_title.setStyleSheet(
            "font-size: 22px; font-weight: 800; color: #FFFFFF;"
            " border: none; background: transparent; line-height: 1.3;"
        )
        hero_layout.addWidget(hero_title)

        hero_sub = QLabel("Access your tools and recent projects to pick up right where you left off.")
        hero_sub.setStyleSheet(
            "font-size: 13px; color: #9BA3B5; border: none; background: transparent;"
        )
        hero_sub.setWordWrap(True)
        hero_layout.addWidget(hero_sub)
        hero_layout.addStretch()
        cv.addWidget(hero)

        # ── Quick Actions ────────────────────────────────────────────────────
        cv.addLayout(_section_title("⚡", "Quick Actions"))

        self.new_card = ActionCard("➕", "Create New Project", "Start a fresh exam template from scratch")
        self.new_card.clicked.connect(self.handle_new_project)
        cv.addWidget(self.new_card)

        self.open_card = ActionCard("📂", "Open Existing Project", "Browse your local and cloud saved files")
        self.open_card.clicked.connect(self.handle_open_project)
        cv.addWidget(self.open_card)

        # ── Recent Projects ──────────────────────────────────────────────────
        recent_hdr = _section_title("📅", "Recent Projects")
        view_all_btn = QPushButton("View all")
        view_all_btn.setFlat(True)
        view_all_btn.setStyleSheet(
            "QPushButton { color: #f97316; font-size: 13px; font-weight: 600;"
            " border: none; background: transparent; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        view_all_btn.clicked.connect(self.handle_open_project)
        recent_hdr.addWidget(view_all_btn)
        cv.addLayout(recent_hdr)

        # Recents card
        self.recents_card = QFrame()
        self.recents_card.setStyleSheet(
            "QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB;"
            " border-radius: 12px; }"
        )
        self.recents_v = QVBoxLayout(self.recents_card)
        self.recents_v.setContentsMargins(16, 4, 16, 4)
        self.recents_v.setSpacing(0)

        # Table header
        tbl_hdr = QHBoxLayout()
        tbl_hdr.setContentsMargins(0, 8, 0, 8)
        tbl_hdr.setSpacing(12)
        for col_txt, stretch in [("PROJECT NAME", 2), ("LAST MODIFIED", 1), ("ACTION", 0)]:
            h = QLabel(col_txt)
            h.setStyleSheet(
                "font-size: 10px; font-weight: 700; color: #9CA3AF;"
                " letter-spacing: 0.5px; border: none;"
            )
            tbl_hdr.addWidget(h, stretch)
        self.recents_v.addLayout(tbl_hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #F3F4F6; border: none; background: #F3F4F6; max-height: 1px;")
        self.recents_v.addWidget(sep)

        self.recents_rows_widget = QWidget()
        self.recents_rows_widget.setStyleSheet("background: transparent;")
        self.recents_rows_layout = QVBoxLayout(self.recents_rows_widget)
        self.recents_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.recents_rows_layout.setSpacing(0)
        self.recents_v.addWidget(self.recents_rows_widget)
        cv.addWidget(self.recents_card)

        cv.addStretch()
        v.addWidget(content)
        scroll.setWidget(page)
        outer.addWidget(scroll)

        self.refresh_recents()

    def refresh_recents(self):
        # Clear
        for i in reversed(range(self.recents_rows_layout.count())):
            w = self.recents_rows_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        recents = self.pm.get_recent_projects()

        if not recents:
            empty = QLabel("No recent projects found. Build something great! ✨")
            empty.setStyleSheet(
                "color: #9CA3AF; font-style: italic; font-size: 13px; border: none;"
                " padding: 20px 0;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.recents_rows_layout.addWidget(empty)
            return

        for p in recents[:8]:   # show max 8 recent
            row = RecentProjectRow(p)
            row.open_requested.connect(self.open_existing)
            self.recents_rows_layout.addWidget(row)

    # ── Handlers ─────────────────────────────────────────────────────────────
    def handle_new_project(self):
        root = QFileDialog.getExistingDirectory(self, "Select Folder for New Project")
        if root:
            name, ok = QInputDialog.getText(self, "Project Name", "Enter project name:")
            if ok and name:
                proj = self.pm.create_project(name, root)
                self.project_opened.emit(proj)
                self.refresh_recents()

    def handle_open_project(self):
        path = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if path:
            self.open_existing(path)

    def open_existing(self, path: str):
        if not path:
            return
        proj = self.pm.load_project(path)
        if proj:
            self.project_opened.emit(proj)
        else:
            QMessageBox.warning(
                self, "Open Failed",
                "Could not load the project.\nThe folder may have been moved or deleted."
            )

    # Kept for back-compat (called from main_window or other places)
    def open_last_project(self):
        recents = self.pm.get_recent_projects()
        if not recents:
            QMessageBox.information(self, "No Recent Projects", "No recent projects found.")
            return
        self.open_existing(recents[0].get("path", ""))
