from __future__ import annotations

import json
import os
import datetime
from datetime import datetime as _dt

CURRENT_PROJECT_VERSION = 1

class ProjectManager:
    """
    Manages project sessions and recent file history.
    """
    def __init__(self, settings_dir="config"):
        self.settings_dir = settings_dir
        self.recents_file = os.path.join(settings_dir, "recents.json")
        self.current_project = None
        self._ensure_config()

    def _ensure_config(self):
        os.makedirs(self.settings_dir, exist_ok=True)
        if not os.path.exists(self.recents_file):
            self._save_recents([])

    def _load_recents(self):
        try:
            with open(self.recents_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, PermissionError):
            return []
        except json.JSONDecodeError as e:
            print(f"[project.py] Corrupted recents file: {e}")
            return []

    def _save_recents(self, recents):
        with open(self.recents_file, 'w') as f:
            json.dump(recents, f, indent=4)

    def get_recents(self) -> list[dict]:
        return self._load_recents()

    def get_recent_projects(self):
        return self._load_recents()

    def create_project(self, name: str, path: str) -> dict | None:
        """Creates a new project structure"""
        full_path = os.path.join(path, name)
        os.makedirs(full_path, exist_ok=True)

        # Subdirs
        os.makedirs(os.path.join(full_path, "pdfs"), exist_ok=True)
        os.makedirs(os.path.join(full_path, "questions"), exist_ok=True)
        os.makedirs(os.path.join(full_path, "papers"), exist_ok=True)

        # Write project.json manifest
        manifest = {
            "version": CURRENT_PROJECT_VERSION,
            "name": name,
            "created": _dt.now().isoformat(),
            "last_opened": _dt.now().isoformat(),
            "iconic_exam_maker": True,
        }
        manifest_path = os.path.join(full_path, "project.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        project_data = {
            "name": name,
            "path": full_path,
            "created": _dt.now().isoformat(),
            "last_opened": _dt.now().isoformat(),
            "files": []
        }

        self.current_project = project_data
        self._add_to_recents(project_data)
        return project_data

    def load_project(self, project_path: str) -> dict | None:
        # In a real app, logic to validate project file would go here
        # For now, we assume folder existence is enough
        if os.path.exists(project_path):
            # Check for project.json manifest
            manifest_path = os.path.join(project_path, "project.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    if not manifest.get("iconic_exam_maker"):
                        return None  # Not a valid Iconic project
                    version = manifest.get("version", 1)
                    if version > CURRENT_PROJECT_VERSION:
                        print(f"Warning: Project was created with a newer version ({version})")
                    # Update last_opened
                    manifest["last_opened"] = _dt.now().isoformat()
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, indent=2)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Warning: Could not read project manifest: {e}")

            name = os.path.basename(project_path)
            project_data = {
                "name": name,
                "path": project_path,
                "last_opened": _dt.now().isoformat()
            }
            self.current_project = project_data
            self._add_to_recents(project_data)
            return project_data
        return None

    def _add_to_recents(self, project_data):
        recents = self._load_recents()
        # Remove if exists (to bump to top)
        recents = [p for p in recents if p["path"] != project_data["path"]]
        recents.insert(0, {
            "name": project_data["name"],
            "path": project_data["path"],
            "last_opened": project_data["last_opened"]
        })
        self._save_recents(recents[:10]) # Keep top 10

    def remove_from_recents(self, path: str) -> None:
        """Remove a path from the recents list."""
        recents = self.get_recents()
        recents = [r for r in recents if r.get("path") != path]
        try:
            recents_file = os.path.join(self.settings_dir, "recents.json")
            with open(recents_file, "w", encoding="utf-8") as f:
                json.dump(recents, f, indent=2)
        except (OSError, PermissionError) as e:
            print(f"Could not update recents: {e}")

    def save_question(self, pdf_name: str, question_data: dict, image: object) -> tuple[bool, str | None]:
        """
        Saves a single question to the project directory with sequential numbering.
        'image' can be PIL Image or bytes.
        """
        if not self.current_project:
            return False, None

        # 1. Ensure PDF-specific subdirectory
        safe_pdf_name = "".join([c if c.isalnum() else "_" for c in pdf_name])
        q_root = os.path.join(self.current_project["path"], "questions", safe_pdf_name)
        os.makedirs(q_root, exist_ok=True)

        # 2. Get next sequential number
        q_num = self._get_next_q_number(q_root)
        q_id = f"Q{q_num:03d}"

        img_path = os.path.join(q_root, f"{q_id}.png")
        json_path = os.path.join(q_root, f"{q_id}.json")

        # 3. Save Image & Metadata
        try:
            from PIL import Image
            if isinstance(image, Image.Image):
                image.save(img_path, "PNG", dpi=(300, 300))
            else:
                with open(img_path, "wb") as f:
                    f.write(image)

            # Save metadata (tags, marks, label/id)
            question_data["id"] = q_id
            question_data["saved_at"] = _dt.now().isoformat()

            with open(json_path, "w") as f:
                json.dump(question_data, f, indent=4)

            print(f"Question saved as {q_id} in {safe_pdf_name}")
            return True, q_id
        except Exception as e:
            print(f"Error saving question: {e}")
            return False, None

    def _get_next_q_number(self, q_dir):
        """Finds the next available QXXX index in the directory."""
        import re
        max_num = 0
        if not os.path.exists(q_dir):
            return 1

        for f in os.listdir(q_dir):
            if f.startswith("Q") and f.endswith(".png"):
                match = re.search(r"Q(\d+)", f)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
        return max_num + 1
