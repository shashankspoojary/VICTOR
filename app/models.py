from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    tts: bool = False
    imgbase64: Optional[str] = None
