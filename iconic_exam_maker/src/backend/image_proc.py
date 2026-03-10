from PIL import Image
import cv2
import numpy as np

def clean_image(pil_image):
    """
    Apply advanced deskewing and denoising to a PIL Image.
    Returns: Cleaned PIL Image
    """
    img = np.array(pil_image)
    
    # 1. Convert to Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img
        
    # 2. Deskewing
    coords = np.column_stack(np.where(gray > 0)) # Assuming black text on white, this might be inverted?
    # Actually, usually inverted for deskew (white text on black).
    # Standard documents are white background (255).
    # We need to invert for minAreaRect
    
    thresh_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh_inv > 0))
    
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # Rotate if significant skew and not just noise
        if abs(angle) > 0.5 and abs(angle) < 45:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            # Re-get gray after rotation
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img

    # 3. Denoise & Threshold
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
                                   
    return Image.fromarray(binary)
