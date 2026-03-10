# Integration Guide: Review Dialog

This guide explains how to integrate the ReviewDialog into your workflow.

## Overview

The `ReviewDialog` allows users to review detected questions one-by-one and approve/reject them before saving to the question bank.

## Basic Usage

```python
from src.ui.review_dialog import ReviewDialog

# After auto-extraction, collect all cropped image paths
image_files = [
    "questions/Q001.png",
    "questions/Q002.png",
    "questions/Q003.png"
]

# Show review dialog
review_dialog = ReviewDialog(image_files, parent=self)

def on_review_completed(summary):
    kept = summary['kept']
    rejected = summary['rejected']
    print(f"Review complete: {kept} kept, {rejected} rejected")
    # Rejected files are moved to _rejected folder automatically

review_dialog.review_completed.connect(on_review_completed)
review_dialog.exec()
```

## Integration Points

### 1. After Auto-Extraction (Editor)

When auto-extraction completes and saves cropped images:

```python
def on_extraction_complete(self, saved_files):
    # saved_files is a list of paths to cropped question images
    
    # Option 1: Always show review
    self.show_review_dialog(saved_files)
    
    # Option 2: Ask user first
    reply = QMessageBox.question(
        self, "Review Questions",
        "Would you like to review the extracted questions?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    
    if reply == QMessageBox.StandardButton.Yes:
        self.show_review_dialog(saved_files)

def show_review_dialog(self, image_files):
    from src.ui.review_dialog import ReviewDialog
    
    dialog = ReviewDialog(image_files, self)
    dialog.review_completed.connect(self.on_review_completed)
    dialog.exec()

def on_review_completed(self, summary):
    QMessageBox.information(
        self, "Review Complete",
        f"Questions kept: {summary['kept']}\n"
        f"Questions rejected: {summary['rejected']}"
    )
```

### 2. Batch Review from Question Bank

Allow users to review all questions in a folder:

```python
def review_question_bank(self):
    import os
    from src.ui.review_dialog import ReviewDialog
    
    # Get all images from questions folder
    questions_dir = "questions"
    image_files = []
    
    for root, dirs, files in os.walk(questions_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    
    if not image_files:
        QMessageBox.information(self, "No Questions", "No questions found to review")
        return
    
    dialog = ReviewDialog(image_files, self)
    dialog.exec()
```

## Keyboard Shortcuts

The review dialog supports these shortcuts:
- **Enter/Space**: Keep current question
- **Delete/X**: Reject current question  
- **Left Arrow**: Go back to previous question

## Customization

### Skip Review Option

Add a checkbox to let users skip the review:

```python
# In your UI
self.skip_review_checkbox = QCheckBox("Skip review (auto-approve all)")

# In your extraction handler
if not self.skip_review_checkbox.isChecked():
    self.show_review_dialog(saved_files)
```

### Custom Rejected Folder

By default, rejected files go to `_rejected` folder. To customize:

```python
# Modify ReviewDialog.reject_current() method
rejected_dir = os.path.join(parent_dir, "custom_rejected_folder")
```

## Notes

- Rejected files are moved, not deleted (safer for recovery)
- The dialog is modal (blocks interaction with parent window)
- Review progress is shown in the status label
- Images are automatically scaled to fit the display
