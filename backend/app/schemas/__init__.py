import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.taxonomy import ERROR_TAG_CODES

Layer = Literal["layer_1", "layer_2"]
NoiseLevel = Literal["quiet", "moderate", "noisy"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth / users -----------------------------------------------------------

class LoginIn(BaseModel):
    email: str
    password: str


class MeOut(ORMModel):
    id: uuid.UUID
    email: str
    role: str
    can_layer_1: bool
    can_layer_2: bool


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    role: str
    can_layer_1: bool
    can_layer_2: bool
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    can_layer_1: bool = False
    can_layer_2: bool = False


class UserPatch(BaseModel):
    is_active: bool | None = None
    can_layer_1: bool | None = None
    can_layer_2: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8)


# --- passages ---------------------------------------------------------------

class TokenOut(ORMModel):
    word_index: int
    printed_word: str


class PassageCreate(BaseModel):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    urdu_text: str = Field(min_length=1)


class PassageOut(ORMModel):
    id: uuid.UUID
    code: str
    title: str
    urdu_text: str
    created_at: datetime
    tokens: list[TokenOut]
    # Recordings (including withdrawn ones) that use this passage; >0 blocks deletion.
    recording_count: int = 0


# --- ingestion / recordings -------------------------------------------------

class ScanFile(BaseModel):
    filename: str
    size_bytes: int
    duration_seconds: float | None


class IngestIn(BaseModel):
    passage_id: uuid.UUID
    passage_attempt: int = Field(ge=1, le=2)
    grade: int = Field(ge=1, le=12)
    gender: str = Field(min_length=1)
    first_language: str = Field(min_length=1)
    school_type: str = Field(min_length=1)
    noise_level: NoiseLevel
    interruption: bool = False
    assessor_notes: str | None = None


class WithdrawIn(BaseModel):
    reason: str = Field(min_length=1)


class RecordingOut(ORMModel):
    id: uuid.UUID
    source: str
    source_ref: str
    duration_seconds: Decimal | None
    passage_id: uuid.UUID
    passage_attempt: int
    grade: int
    gender: str
    first_language: str
    school_type: str
    noise_level: str
    interruption: bool
    assessor_notes: str | None
    ingested_at: datetime
    withdrawn_at: datetime | None
    withdrawn_reason: str | None


class RecordingListItem(RecordingOut):
    passage_code: str
    task_statuses: dict[str, str]


class StatsOut(BaseModel):
    recordings_total: int
    tasks_available: int
    tasks_in_progress: int
    tasks_submitted: int
    annotators: int
    last_export_at: datetime | None


# --- tasks ------------------------------------------------------------------

class TaskOut(BaseModel):
    id: uuid.UUID
    layer: Layer
    status: str
    checked_out_at: datetime | None
    lease_expires_at: datetime | None
    recording_id: uuid.UUID
    passage_code: str
    duration_seconds: float | None
    audio_url: str
    # Only populated for layer_2: Layer 1 transcribers never see the passage.
    tokens: list[TokenOut] | None = None


class DraftIn(BaseModel):
    payload: dict[str, Any]


class DraftOut(BaseModel):
    payload: dict[str, Any]
    updated_at: datetime


class DraftSaved(BaseModel):
    updated_at: datetime
    lease_expires_at: datetime | None


def _seconds(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


class MarksIn(BaseModel):
    first_word_mark_seconds: Decimal = Field(ge=0)
    last_word_mark_seconds: Decimal = Field(ge=0)
    boundary_60s_mark_seconds: Decimal = Field(ge=0)

    @field_validator("first_word_mark_seconds", "last_word_mark_seconds", "boundary_60s_mark_seconds")
    @classmethod
    def _three_places(cls, v: Decimal) -> Decimal:
        return _seconds(v)


class Layer1Submit(MarksIn):
    transcript_urdu: str


class WordJudgement(BaseModel):
    word_index: int = Field(ge=1)
    is_error: bool
    error_tag: str | None = None

    @field_validator("error_tag")
    @classmethod
    def _known_tag(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in ERROR_TAG_CODES:
            raise ValueError(f"unknown error tag {v!r}")
        return v


class InsertionIn(BaseModel):
    after_word_index: int = Field(ge=0)
    inserted_text: str = Field(min_length=1)
    position_within_slot: int = Field(ge=1)


class Layer2Submit(MarksIn):
    words: list[WordJudgement]
    insertions: list[InsertionIn] = []


class SubmitOut(BaseModel):
    annotation_id: uuid.UUID
    task_id: uuid.UUID
    status: str
