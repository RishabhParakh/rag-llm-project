from pydantic import BaseModel
from typing import Optional



class ChatRequest(BaseModel):
    user_message: str
    file_id: str


class ChatResponse(BaseModel):
    response: str

class ResumeUploadResponse(BaseModel):
    file_id: Optional[str] = None
    extracted_name: Optional[str] = None
    summary: Optional[str] = None
    message: Optional[str] = None

