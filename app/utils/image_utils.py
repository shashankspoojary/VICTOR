# app/utils/image_utils.py
import base64
import io
from pathlib import Path
from PIL import Image

def encode_image_to_base64(image_path: Path, max_size: tuple = (1920, 1080)) -> str:
    """Resizes and encodes an image to a base64 string for efficient VLM consumption."""
    if not image_path.exists():
        return ""
        
    try:
        with Image.open(image_path) as img:
            # Convert to RGB to drop alpha channels and reduce token payload size
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[Image Utils] Encoding execution error: {e}")
        return ""