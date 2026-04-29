from pydantic import BaseModel

class DocumentBase(BaseModel):
    file_name: str
    application_id: int

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    storage_path: str

    class Config:
        from_attributes = True