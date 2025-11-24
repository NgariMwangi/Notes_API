from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    tags: Optional[List[str]] = Field(default=None)

    @validator("tags")
    def validate_tags(cls, tags):
        if tags is None:
            return tags
        for tag in tags:
            if not isinstance(tag, str) or not (0 < len(tag) <= 30):
                raise ValueError("Each tag must be a non-empty string up to 30 characters")
        return tags


class NoteCreate(NoteBase):
    pass


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    tags: Optional[List[str]] = Field(default=None)


class Note(NoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotesListResponse(BaseModel):
    total: int
    items: List[Note]


class RecentlyViewedResponse(BaseModel):
    items: List[Note]

