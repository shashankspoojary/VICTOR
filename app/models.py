from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str
    message: str
    use_search: bool = False

class ChatResponse(BaseModel):
    # Used for non-streaming fallback or metadata if needed
    status: str