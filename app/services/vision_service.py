# app/services/vision_service.py
import os
from app.services.vlm_service import VLMService
from app.services.screen_analysis_service import ScreenAnalysisService
from app.services.window_analysis_service import WindowAnalysisService
from app.utils.screen_utils import capture_primary_screen
from app.utils.image_utils import encode_image_to_base64

class VisionService:
    """Primary orchestrator for generating visual understanding representations from desktop interfaces."""
    
    def __init__(self):
        self.vlm_service = VLMService()
        self.screen_analysis = ScreenAnalysisService()
        self.window_analysis = WindowAnalysisService()

    async def analyze_current_screen(self, query: str = "Describe what is on the screen in detail.") -> str:
        window_info = self.window_analysis.get_active_window_info()
        active_app = window_info.get('title', 'Unknown Application Environment')
        
        screenshot_path = capture_primary_screen()
        if not screenshot_path or not screenshot_path.exists():
            return "Execution Blocked: Visual systems failed to allocate memory for screen capture."

        base64_image = encode_image_to_base64(screenshot_path)
        if not base64_image:
            return "Execution Blocked: Image encoding processor encountered a structural fault."

        prompt = (
            f"You are a sophisticated visual analysis AI logic core.\n"
            f"The user is currently focused on an application titled: '{active_app}'.\n\n"
            f"User Objective/Query: {query}\n\n"
            "Analyze the image and provide a highly detailed, technical response addressing the exact state of the interface."
        )

        raw_analysis = await self.vlm_service.analyze_image(base64_image, prompt)
        
        # Immediate cleanup of heavy volatile artifacts
        try:
            if screenshot_path.exists():
                os.remove(screenshot_path)
        except Exception:
            pass

        self.screen_analysis.parse_vlm_output(raw_analysis, active_app)
        
        return (
            f"Active Window Frame: {active_app}\n\n"
            f"{raw_analysis}"
        )