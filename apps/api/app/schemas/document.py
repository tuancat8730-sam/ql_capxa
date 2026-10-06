import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DocCategory = Literal[
    "legal", "selection", "contract", "execution", "acceptance", "payment", "other"
]
Confidentiality = Literal["normal", "sensitive"]
ExtractionStatus = Literal["pending", "done", "needs_ocr", "unsupported", "failed"]

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

RESTRICTED_TITLE = "Tài liệu hạn chế"


class UploadUrlRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(ge=1)
    package_id: uuid.UUID | None = None
    # Set when uploading a new version of an existing document.
    parent_document_id: uuid.UUID | None = None


class UploadTarget(BaseModel):
    url: str
    method: str
    headers: dict[str, str]


class UploadUrlResponse(BaseModel):
    document_id: uuid.UUID
    file_key: str
    version: int
    upload: UploadTarget
    expires_in: int
    max_bytes: int


class FileRef(BaseModel):
    """What the browser reports after its direct upload to object storage."""

    document_id: uuid.UUID
    file_key: str
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=150)
    size_bytes: int = Field(ge=1)
    sha256: Sha256 | None = None


class DocumentMeta(BaseModel):
    doc_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    category: DocCategory | None = None
    doc_no: str | None = Field(default=None, max_length=100)
    doc_date: date | None = None
    issuer: str | None = Field(default=None, max_length=300)
    confidentiality: Confidentiality = "normal"
    contract_id: uuid.UUID | None = None
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    notes: str | None = None


class DocumentCreate(FileRef, DocumentMeta):
    package_id: uuid.UUID | None = None


class VersionCreate(FileRef):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    doc_no: str | None = Field(default=None, max_length=100)
    doc_date: date | None = None
    notes: str | None = None


class DocumentUpdate(BaseModel):
    doc_type: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    category: DocCategory | None = None
    doc_no: str | None = Field(default=None, max_length=100)
    doc_date: date | None = None
    issuer: str | None = Field(default=None, max_length=300)
    confidentiality: Confidentiality | None = None
    contract_id: uuid.UUID | None = None
    tags: list[Tag] | None = Field(default=None, max_length=20)
    notes: str | None = None


class DocumentOut(BaseModel):
    """Full record, or a redacted stub (`restricted=True`) for files the caller may not open."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID | None
    restricted: bool = False
    title: str
    confidentiality: Confidentiality
    category: DocCategory | None = None
    doc_type: str | None = None
    doc_no: str | None = None
    doc_date: date | None = None
    issuer: str | None = None
    contract_id: uuid.UUID | None = None
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    version: int | None = None
    is_current: bool | None = None
    extraction_status: ExtractionStatus | None = None
    tags: list[str] = []
    notes: str | None = None
    uploaded_by: uuid.UUID | None = None
    created_at: datetime | None = None


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    is_current: bool
    file_name: str
    size_bytes: int
    uploaded_by: uuid.UUID | None
    created_at: datetime


class DocumentDetail(DocumentOut):
    versions: list[VersionOut] = []


class DownloadOut(BaseModel):
    url: str
    expires_in: int
    file_name: str
    mime_type: str
    inline: bool


class DocTypeOut(BaseModel):
    code: str
    label: str
    category: DocCategory


class AccessUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: str


class AccessIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(max_length=200)


class AccessOut(BaseModel):
    users: list[AccessUser]


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    stage_code: str
    doc_type: str
    title: str
    required: bool
    status: Literal["missing", "received", "not_applicable"]
    document_id: uuid.UUID | None
    document_title: str | None = None
    document_restricted: bool = False
    due_date: date | None
    overdue: bool = False
    note: str | None


class ChecklistOut(BaseModel):
    items: list[ChecklistItemOut]
    required_total: int
    required_done: int
    completion_pct: float


class ChecklistItemUpdate(BaseModel):
    status: Literal["missing", "received", "not_applicable"] | None = None
    document_id: uuid.UUID | None = None
    due_date: date | None = None
    note: str | None = None
