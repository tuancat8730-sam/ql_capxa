import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

DocKind = Literal["CV", "BC", "TB", "BB", "QD", "TT", "KH"]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DocNumberIn(BaseModel):
    doc_kind: DocKind
    subject: Subject
    # defaults to today (Vietnam); its year decides which yearly sequence the number comes from
    issued_date: date | None = None


class DocNumberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    year: int
    doc_kind: DocKind
    seq: int
    doc_no: str
    subject: str
    issued_date: date
    created_by_name: str | None
    created_at: datetime
