import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.utils.exporter import PDFExporter

# Mock Data
questions = [
    {"img_path": "test_q1.png"}, # Won't exist, code should handle gracefully
]

# Config reflecting user's defaults
config = {
    "subject": "PHYSICS",
    "exam_series": "Final Exam Series",
    "paper_number": "1",
    "duration": "01 hour",
    "paper_code_1": "01",
    "paper_code_2": "T",
    "paper_code_3": "I",
    "lecturer_name": "M.M.JEZEER AHAMED",
    "lecturer_qualification": "B.sc (Engineering)",
    "logo_path": "logo.png"
}

output_path = "test_output.pdf"

print("Starting PDF Generation Test...")
try:
    success = PDFExporter.generate_exam_pdf(questions, output_path, config=config)
    if success:
        print(f"SUCCESS: PDF generated at {output_path}")
    else:
        print("FAILURE: PDFExporter returned False")
except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
