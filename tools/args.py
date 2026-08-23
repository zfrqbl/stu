"""Typed argument models for native tools."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryCreateArgs(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)


class MemorySearchArgs(BaseModel):
    query: str | None = None
    limit: int = Field(20, ge=1, le=100)


class MemoryGetArgs(BaseModel):
    memory_id: str


class ProjectGetArgs(BaseModel):
    pass


class WorkspaceListArgs(BaseModel):
    path: str = ""


class WorkspaceReadArgs(BaseModel):
    path: str


class WorkspaceWriteArgs(BaseModel):
    path: str
    content: str


class SystemStatusArgs(BaseModel):
    pass
