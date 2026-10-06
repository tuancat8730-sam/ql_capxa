import uuid
from typing import Literal

from pydantic import BaseModel

SearchKind = Literal["package", "contract", "document", "risk", "issue"]


class SearchHit(BaseModel):
    kind: SearchKind
    id: uuid.UUID
    title: str
    snippet: str | None = None
    package_id: uuid.UUID | None = None
    package_number: int | None = None
    # extra context shown next to the title (document type, contract number, risk code, ...)
    subtitle: str | None = None


class SearchGroup(BaseModel):
    kind: SearchKind
    total: int
    items: list[SearchHit]


class SearchOut(BaseModel):
    query: str
    groups: list[SearchGroup]
