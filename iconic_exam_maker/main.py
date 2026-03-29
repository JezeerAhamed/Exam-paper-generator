import sys
import os
import json
import traceback
import shutil
import logging
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QCheckBox
from PySide6.QtGui import QIcon
from src.ui.main_window import MainWindow
from src.utils.styles import load_stylesheet

REQUIRED_FONTS = ["times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf", "latha.ttf", "iskpota.ttf"]

def _load_config(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.warning("Config load failed: %s", e)
        return None

def _save_config(config_path, data):
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except (OSError, PermissionError) as e:
        logging.error("Config save failed: %s", e)

def _get_missing_fonts(font_dir):
    missing = []
    for fname in REQUIRED_FONTS:
        if not os.path.exists(os.path.join(font_dir, fname)):
            missing.append(fname)
    return missing

def ensure_app_folders():
    os.makedirs("config", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    config_path = os.path.join("config", "config.json")
    if not os.path.exists(config_path):
        default_config = {
            "institute": {
                "name": "ICONIC ACADEMY",
                "lecturer_name": "M.M.JEZEER AHAMED",
                "lecturer_qualification": "B.sc (Engineering)",
                "lecturer_university": "UOM",
                "logo_path": "logo.png"
            },
            "exam_defaults": {
                "subject": "PHYSICS",
                "exam_series": "Final Exam Series",
                "paper_number": "1",
                "duration": "01 hour",
                "paper_code": ["01", "T", "I"],
                "part_code": "I",
                "footer_quote": "“Find simplicity in the universe”"
            },
            "output_dirs": {
                "questions": "questions",
                "exam_papers": "exam_papers",
                "mcqs": "mcqs"
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for rel in data.get("output_dirs", {}).values():
                if rel:
                    os.makedirs(rel, exist_ok=True)
        except (OSError, json.JSONDecodeError) as e:
            logging.warning("Folder setup issue: %s", e)
    # Font availability check
    font_dir = os.path.join("assets", "fonts")
    missing = _get_missing_fonts(font_dir)
    if missing:
        log_path = os.path.join("logs", "font_warnings.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} Missing fonts: {', '.join(missing)}\n")

def maybe_prompt_install_fonts(parent=None):
    font_dir = os.path.join("assets", "fonts")
    missing = _get_missing_fonts(font_dir)
    if not missing:
        return

    config_path = os.path.join("config", "config.json")
    config = _load_config(config_path)
    if config and config.get("app", {}).get("suppress_font_prompt", False):
        return

    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setWindowTitle("Missing Fonts")
    msg.setText("Some required fonts are missing. This can affect layout and Sinhala/Tamil rendering.")
    msg.setInformativeText(
        "Missing: " + ", ".join(missing) +
        "\n\nChoose 'Install Fonts...' to copy .ttf/.otf files into assets/fonts."
    )
    install_btn = msg.addButton("Install Fonts...", QMessageBox.ButtonRole.AcceptRole)
    msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
    dont_ask = QCheckBox("Don't ask again")
    msg.setCheckBox(dont_ask)
    msg.exec()

    if dont_ask.isChecked() and config is not None:
        config.setdefault("app", {})["suppress_font_prompt"] = True
        _save_config(config_path, config)

    if msg.clickedButton() != install_btn:
        return

    from src.utils.platform_utils import get_system_font_dir
    font_dir_sys = get_system_font_dir()
    start_dir = font_dir_sys if os.path.isdir(font_dir_sys) else ""

    files, _ = QFileDialog.getOpenFileNames(
        parent,
        "Select Font Files",
        start_dir,
        "Font Files (*.ttf *.otf)"
    )
    if not files:
        return

    os.makedirs(font_dir, exist_ok=True)
    copy_errors = []
    for fpath in files:
        try:
            dest = os.path.join(font_dir, os.path.basename(fpath))
            shutil.copy2(fpath, dest)
        except Exception as e:
            copy_errors.append(f"{os.path.basename(fpath)} ({e})")

    missing_after = _get_missing_fonts(font_dir)
    if copy_errors:
        QMessageBox.warning(
            parent,
            "Font Install Warnings",
            "Some fonts could not be copied:\n" + "\n".join(copy_errors)
        )

    if missing_after:
        QMessageBox.warning(
            parent,
            "Fonts Still Missing",
            "Some required fonts are still missing:\n" + ", ".join(missing_after)
        )
    else:
        QMessageBox.information(
            parent,
            "Fonts Installed",
            "All required fonts are now available."
        )

def validate_environment() -> list[str]:
    """Validate that all required libraries are importable."""
    errors = []
    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10+ required; found {sys.version}")
    for lib in ("fitz", "PIL", "cv2", "numpy"):
        try:
            __import__(lib)
        except ImportError:
            errors.append(f"Required library missing: {lib} — run: pip install -r requirements.txt")
    return errors


def validate_config(config_path: str) -> bool:
    """Validate config JSON. Back up and remove corrupted files. Returns True if OK."""
    if not os.path.exists(config_path):
        return True  # Will be created on first run
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except json.JSONDecodeError as e:
        backup = config_path + ".corrupted"
        try:
            shutil.copy2(config_path, backup)
            os.remove(config_path)
            logging.warning("config.json was corrupted, backed up to %s: %s", backup, e)
        except OSError as oe:
            logging.error("Could not backup corrupted config: %s", oe)
        return False


def setup_global_exception_handler(app):
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        os.makedirs("logs", exist_ok=True)
        log_path = os.path.join("logs", "crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"{datetime.now().isoformat()}\n")
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        QMessageBox.critical(
            None,
            "Unexpected Error",
            f"The app encountered an error and needs to close.\n\nDetails saved to:\n{log_path}"
        )
        app.quit()
    sys.excepthook = handle_exception

def main():
    from src.utils.log_config import configure_logging
    configure_logging()
    logger = logging.getLogger(__name__)

    env_errors = validate_environment()
    if env_errors:
        for err in env_errors:
            logger.error(err)
        try:
            import tkinter as tk
            import tkinter.messagebox as mb
            root = tk.Tk()
            root.withdraw()
            mb.showerror("Startup Error", "\n".join(env_errors))
            root.destroy()
        except Exception:
            pass
        sys.exit(1)

    config_path = os.path.join("config", "config.json")
    validate_config(config_path)

    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(app_root)
    # Ensure High DPI scaling
    os.environ["QT_FONT_DPI"] = "96"

    ensure_app_folders()
    app = QApplication(sys.argv)
    setup_global_exception_handler(app)
    
    # App Icon
    icon_path = os.path.join("assets", "logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Load Theme
    app.setStyleSheet(load_stylesheet())
    
    window = MainWindow()
    window.show()
    maybe_prompt_install_fonts(window)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
