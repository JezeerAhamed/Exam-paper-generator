import os

def load_stylesheet():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "styles.qss")
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""
