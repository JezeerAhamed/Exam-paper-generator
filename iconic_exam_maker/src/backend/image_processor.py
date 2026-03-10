import cv2
import numpy as np
from PIL import Image


def clean_image(pil_image):
    """
    Enhance the image: Deskew, Contrast, Denoise.
    Ported from R&D version for high-quality question extraction.
    """
    # Convert PIL -> OpenCV
    img = np.array(pil_image)
    
    # 1. Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    # 2. DESKEW (Straighten Text)
    # Find all black pixels (text) to calculate orientation
    coords = np.column_stack(np.where(gray < 200))  # Threshold for dark text
    if len(coords) > 10:  # Need enough points
        angle = cv2.minAreaRect(coords)[-1]
        
        # Correct the angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # Only rotate if the skew is noticeable but not extreme (avoid flipping)
        if abs(angle) > 0.2 and abs(angle) < 15:
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            # Use white border (255) for filling empty space after rotation
            gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, 
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    # 3. Denoise (Fast)
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    
    # 4. Contrast / Binarization (Adaptive Threshold for clean text)
    binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
                                   
    return Image.fromarray(binary)


def auto_enhance(pil_image, aggressive=False):
    """
    Quick enhancement for cropped questions.
    
    Args:
        pil_image: PIL Image to enhance
        aggressive: If True, applies full clean_image processing
    
    Returns:
        Enhanced PIL Image
    """
    if aggressive:
        return clean_image(pil_image)
    
    # Light enhancement - just denoise and sharpen
    img = np.array(pil_image)
    
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    
    # Sharpen
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    return Image.fromarray(sharpened)
