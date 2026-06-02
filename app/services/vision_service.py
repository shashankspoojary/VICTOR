import os
import sys
import logging
from typing import Optional

import config
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.ai_service = AIService()

    def analyze_frame(self, image_base64: str, prompt: str = "What do you see?", system_override: str = "") -> str:
        try:
            # Clean the incoming base64 data string (remove comma split header if present)
            clean_b64 = image_base64.split(",")[-1] if "," in image_base64 else image_base64

            if not system_override:
                system_prompt = (
                    "You are operating as VICTOR's visual sensors, helping owner Shashank see his "
                    "desktop environment, screenshots, or webcam frames clearly. "
                    "You must respond concisely and intelligently."
                )
            else:
                system_prompt = system_override

            return self.ai_service.analyze_image(
                image_base64=clean_b64,
                prompt=prompt,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.error(f"Visual compilation failed: {e}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Ensure the root project directory is in sys.path so we can import 'config' and 'app.*'
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    logger.info("Initializing VisionService for testing...")
    
    # Check configuration variables
    logger.info(f"Checking configuration... config module loaded: {hasattr(config, '__name__')}")

    from unittest.mock import patch

    # Mock assertion statement using a generic 1-pixel base64 placeholder string
    with patch.object(AIService, 'analyze_image', return_value="Mock response") as mock_analyze:
        try:
            vision_service = VisionService()
            
            test_b64 = "data:image/jpeg;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
            logger.info("Running mock assertion statement with test frame...")
            
            result = vision_service.analyze_frame(image_base64=test_b64)
            
            # Assertions to prove VLM routing hook functions cleanly
            mock_analyze.assert_called_once()
            called_kwargs = mock_analyze.call_args.kwargs
            
            assert called_kwargs['image_base64'] == "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7", "Base64 was not cleaned properly"
            assert "VICTOR" in called_kwargs['system_prompt'], "System prompt does not contain expected context"
            assert "Shashank" in called_kwargs['system_prompt'], "System prompt does not contain owner's name"
            
            logger.info("Success! The VLM routing hook functions cleanly.")
        except AssertionError as e:
            logger.error(f"Assertion failed: {e}")
        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
