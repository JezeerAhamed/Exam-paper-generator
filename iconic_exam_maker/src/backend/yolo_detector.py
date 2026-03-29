"""
YOLO-based Question Detector Module.
Uses YOLOv8m for automatic question detection in PDF pages.
"""

import json
import os
import threading

import numpy as np
from PIL import Image

YOLO = None
_YOLO_IMPORT_ATTEMPTED = False
_YOLO_IMPORT_ERROR = None
_yolo_import_lock = threading.Lock()


def _get_yolo_class():
    """
    Lazy import ultralytics.YOLO so app startup does not fail if AI deps are slow/missing.
    """
    global YOLO, _YOLO_IMPORT_ATTEMPTED, _YOLO_IMPORT_ERROR
    if _YOLO_IMPORT_ATTEMPTED:
        return YOLO

    with _yolo_import_lock:
        if _YOLO_IMPORT_ATTEMPTED:
            return YOLO

        _YOLO_IMPORT_ATTEMPTED = True
        try:
            from ultralytics import YOLO as yolo_class

            YOLO = yolo_class
        except KeyboardInterrupt as e:
            # User interrupted heavy import; continue app without AI.
            _YOLO_IMPORT_ERROR = e
            YOLO = None
            print("Warning: YOLO import interrupted. AI detection disabled for this session.")
        except Exception as e:
            _YOLO_IMPORT_ERROR = e
            YOLO = None
            print(f"Warning: ultralytics import failed: {e}. AI detection disabled.")
    return YOLO


def _iter_candidate_config_paths():
    """Yield likely config locations for ai_detection settings."""
    module_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(module_dir, "..", "..", ".."))
    app_root = os.path.abspath(os.path.join(module_dir, "..", ".."))

    base_dirs = [os.getcwd(), project_root, app_root]
    relative_candidates = [
        os.path.join("config", "config.json"),
        os.path.join("iconic_exam_maker", "config", "config.json"),
    ]

    seen = set()
    for base in base_dirs:
        for rel in relative_candidates:
            path = os.path.abspath(os.path.join(base, rel))
            if path in seen:
                continue
            seen.add(path)
            yield path


def load_ai_detection_config():
    """
    Load ai_detection config from the first valid config file.

    Returns:
        tuple[dict, str | None]: (ai_detection dict, config path used)
    """
    for config_path in _iter_candidate_config_paths():
        if not os.path.exists(config_path):
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            ai_config = config.get("ai_detection")
            if isinstance(ai_config, dict):
                return ai_config, config_path
        except Exception as e:
            print(f"Warning: could not read config '{config_path}': {e}")
    return {}, None


class YOLOQuestionDetector:
    """
    Detects questions in PDF page images using a YOLO model.
    """

    def __init__(self, model_path=None, confidence_threshold=None):
        """
        Initialize the YOLO detector.

        Args:
            model_path: Path to the YOLO model file. If None, loads from config.
            confidence_threshold: Minimum confidence for detections (0.0 - 1.0).
        """
        self.model = None
        self.ai_config, self.config_path = load_ai_detection_config()
        self.enabled = bool(self.ai_config.get("enabled", True))

        self.model_path = model_path or self.ai_config.get("model_path", "")

        if confidence_threshold is None:
            confidence_threshold = self.ai_config.get("confidence_threshold", 0.25)
        self.confidence_threshold = float(confidence_threshold)

        self._inference_lock = threading.Lock()
        self._load_model()

    def _resolve_model_path(self, raw_path):
        """Resolve absolute/relative model path against likely roots."""
        if not raw_path:
            return ""

        expanded = os.path.expandvars(os.path.expanduser(str(raw_path).strip()))
        candidates = [expanded]
        if not os.path.isabs(expanded):
            module_dir = os.path.abspath(os.path.dirname(__file__))
            project_root = os.path.abspath(os.path.join(module_dir, "..", "..", ".."))
            app_root = os.path.abspath(os.path.join(module_dir, "..", ".."))
            for base in (os.getcwd(), project_root, app_root):
                candidates.append(os.path.join(base, expanded))

        for candidate in candidates:
            abs_candidate = os.path.abspath(candidate)
            if os.path.exists(abs_candidate):
                return abs_candidate

        return os.path.abspath(candidates[0])

    def _load_model(self):
        """Load the YOLO model."""
        if not self.enabled:
            print("AI detection is disabled in config.")
            return False
        yolo_class = _get_yolo_class()
        if yolo_class is None:
            if _YOLO_IMPORT_ERROR is not None:
                print(f"Warning: AI dependency load failed: {_YOLO_IMPORT_ERROR}")
            else:
                print("Warning: ultralytics is not installed. AI detection is disabled.")
            return False

        self.model_path = self._resolve_model_path(self.model_path)
        if not self.model_path or not os.path.exists(self.model_path):
            print(f"Warning: YOLO model not found at {self.model_path}")
            return False

        try:
            self.model = yolo_class(self.model_path)
            return True
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            return False

    def is_available(self):
        """Check if the detector is ready to use."""
        return self.model is not None

    def detect_questions(self, image):
        """
        Detect questions in an image.

        Args:
            image: PIL Image or numpy array of the page.

        Returns:
            list[dict]: Detection dicts with bbox/confidence/label/type.
        """
        if not self.is_available():
            print("YOLO model not available")
            return []

        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
            img_array = np.array(image)
        else:
            img_array = image

        try:
            with self._inference_lock:
                results = self.model.predict(
                    source=img_array,
                    conf=self.confidence_threshold,
                    verbose=False,
                )

            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                names = getattr(result, "names", {})
                for i in range(len(boxes)):
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = xyxy

                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())

                    if isinstance(names, dict):
                        label = names.get(cls_id, f"class_{cls_id}")
                    elif isinstance(names, list) and 0 <= cls_id < len(names):
                        label = names[cls_id]
                    else:
                        label = f"class_{cls_id}"

                    detections.append(
                        {
                            "bbox": (int(x1), int(y1), int(x2), int(y2)),
                            "confidence": conf,
                            "label": str(label),
                            "type": "yolo_detected",
                        }
                    )

            detections.sort(key=lambda d: d["bbox"][1])
            return detections

        except Exception as e:
            print(f"Error during YOLO detection: {e}")
            import traceback

            traceback.print_exc()
            return []

    def detect_questions_from_pil(self, pil_image):
        """Convenience method to detect questions from a PIL Image."""
        return self.detect_questions(pil_image)


def get_detector(config=None):
    """
    Factory function to get a configured YOLO detector.

    Args:
        config: Optional config dict with ai_detection settings.

    Returns:
        YOLOQuestionDetector instance.
    """
    model_path = None
    confidence = None

    if config:
        ai_config = config.get("ai_detection", {})
        model_path = ai_config.get("model_path")
        confidence = ai_config.get("confidence_threshold")

    return YOLOQuestionDetector(
        model_path=model_path,
        confidence_threshold=confidence,
    )
