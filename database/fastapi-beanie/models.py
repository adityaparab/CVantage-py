"""
CVantage — MongoDB schema (FastAPI + Beanie ODM)
================================================
Production-grade data model for the resume-analysis platform described in PROMPT.md.

Beanie (https://beanie-odm.dev) is the most appropriate ODM for FastAPI:
async (Motor/PyMongo-async), Pydantic-v2-native — models double as API schemas.

Collections
    users          : candidates + admins (role decided by backend RBAC, single login flow)
    resumes        : created or uploaded resumes, stored as json-resume-schema
    analyses       : JD-vs-resume analysis jobs, 3-step pipeline + results
    notifications  : in-app bell notifications (analysis progress / completion)
    aimodels       : admin-managed AI model registry (encrypted API keys)
    authtokens     : refresh / password-reset / email-verify tokens (TTL)
    auditlogs      : admin & security-relevant actions (TTL 400 days)

Conventions
    - created_at / updated_at on every document (updated_at via Replace/SaveChanges events)
    - optimistic locking via Beanie revision_id on mutable aggregates
    - soft delete via deleted_at; partial indexes exclude soft-deleted docs
    - json-resume dates kept as partial-date STRINGS ("2024", "2024-03", "2024-03-01")
    - empty/placeholder fields are stripped by validators — placeholders NEVER persisted
    - secrets (password_hash, api_key_encrypted, token_hash) excluded from API
      serialization via `exclude=True`

Setup:
    from pymongo import AsyncMongoClient          # PyMongo >= 4.9 (or motor)
    from beanie import init_beanie

    client = AsyncMongoClient(settings.mongo_uri)
    await init_beanie(database=client.cvantage, document_models=DOCUMENT_MODELS)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any, Optional

import pymongo
from beanie import Document, Insert, PydanticObjectId, Replace, SaveChanges, before_event
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)
from pymongo import IndexModel

# =============================================================================
# Shared enums & helpers
# =============================================================================

JSON_RESUME_DATE_RE = r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$"

PartialDate = Annotated[
    str, StringConstraints(pattern=JSON_RESUME_DATE_RE, strip_whitespace=True)
]
Str200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Str300 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)]

ALLOWED_RESUME_MIME = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
MAX_RESUME_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    CANDIDATE = "candidate"
    ADMIN = "admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    LINKEDIN = "linkedin"


class ResumeSource(str, Enum):
    CREATED = "created"  # built with the in-app form
    UPLOADED = "uploaded"  # file upload -> AI-parsed


class ResumeAnalysisStatus(str, Enum):
    UNANALYZED = "unanalyzed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadParseStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisStepKey(str, Enum):
    COMPARE = "compare_resume_jd"
    SUGGESTIONS = "generate_suggestions"
    INTERVIEW_QUESTIONS = "prepare_interview_questions"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class NotificationType(str, Enum):
    ANALYSIS_IN_PROGRESS = "analysis_in_progress"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"


class NotificationState(str, Enum):
    ACTIVE = "active"  # shown in the bell
    CLEARED = "cleared"  # visited details page or cleared manually


class AiModelUsage(str, Enum):
    RESUME_PARSING = "resume_parsing"
    ANALYSIS = "analysis"
    FALLBACK = "fallback"


class AiModelStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TokenKind(str, Enum):
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFY = "email_verify"


class SuggestionGroup(str, Enum):
    ATS = "ats_improvement"
    SKILL_EMPHASIS = "skill_emphasis"
    WORDING = "wording"
    SKILL_ADDITION = "skill_addition"
    PROJECT = "project"


class AuditAction(str, Enum):
    USER_LOGIN = "user.login"
    USER_REGISTER = "user.register"
    ADMIN_USER_UPDATE = "admin.user.update"
    ADMIN_USER_DEACTIVATE = "admin.user.deactivate"
    ADMIN_PASSWORD_RESET = "admin.user.password_reset"
    ADMIN_RESUME_DELETE = "admin.resume.delete"
    ADMIN_MODEL_ADD = "admin.model.add"
    ADMIN_MODEL_REMOVE = "admin.model.remove"
    ADMIN_MODEL_KEY_ROTATE = "admin.model.key_rotate"
    RESUME_DELETE = "resume.delete"


def _prune(value: Any) -> Any:
    """Recursively strip empty strings / arrays / objects.

    Guarantees form placeholders are NEVER persisted (PROMPT.md requirement).
    """
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    if isinstance(value, list):
        items = [p for p in (_prune(i) for i in value) if p is not None]
        return items or None
    if isinstance(value, dict):
        out = {k: p for k, p in ((k, _prune(v)) for k, v in value.items()) if p is not None}
        return out or None
    if isinstance(value, BaseModel):
        pruned = _prune(value.model_dump(exclude_none=True))
        return pruned
    return value


# =============================================================================
# json-resume-schema embedded models (https://jsonresume.org/schema)
# All fields optional — empty values are pruned before save, never stored.
# =============================================================================


class JrBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class JrLocation(JrBase):
    address: Optional[Str300] = None
    postal_code: Optional[str] = Field(None, alias="postalCode", max_length=20)
    city: Optional[Str200] = None
    country_code: Optional[
        Annotated[str, StringConstraints(min_length=2, max_length=2, to_upper=True)]
    ] = Field(None, alias="countryCode")
    region: Optional[Str200] = None


class JrProfile(JrBase):
    network: Optional[Str200] = None
    username: Optional[Str200] = None
    url: Optional[HttpUrl] = None


class JrBasics(JrBase):
    name: Optional[Str200] = None
    label: Optional[Str200] = None
    image: Optional[HttpUrl] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=40)
    url: Optional[HttpUrl] = None
    summary: Optional[Annotated[str, StringConstraints(max_length=5000)]] = None
    location: Optional[JrLocation] = None
    profiles: Optional[list[JrProfile]] = None


class JrWork(JrBase):
    name: Optional[Str200] = None  # company
    location: Optional[Str200] = None
    description: Optional[Annotated[str, StringConstraints(max_length=1000)]] = None
    position: Optional[Str200] = None
    url: Optional[HttpUrl] = None
    start_date: Optional[PartialDate] = Field(None, alias="startDate")
    end_date: Optional[PartialDate] = Field(None, alias="endDate")
    summary: Optional[Annotated[str, StringConstraints(max_length=5000)]] = None
    highlights: Optional[list[Str300]] = None


class JrVolunteer(JrBase):
    organization: Optional[Str200] = None
    position: Optional[Str200] = None
    url: Optional[HttpUrl] = None
    start_date: Optional[PartialDate] = Field(None, alias="startDate")
    end_date: Optional[PartialDate] = Field(None, alias="endDate")
    summary: Optional[Annotated[str, StringConstraints(max_length=5000)]] = None
    highlights: Optional[list[Str300]] = None


class JrEducation(JrBase):
    institution: Optional[Str200] = None
    url: Optional[HttpUrl] = None
    area: Optional[Str200] = None
    study_type: Optional[Str200] = Field(None, alias="studyType")
    start_date: Optional[PartialDate] = Field(None, alias="startDate")
    end_date: Optional[PartialDate] = Field(None, alias="endDate")
    score: Optional[str] = Field(None, max_length=50)
    courses: Optional[list[Str300]] = None


class JrAward(JrBase):
    title: Optional[Str200] = None
    date: Optional[PartialDate] = None
    awarder: Optional[Str200] = None
    summary: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None


class JrCertificate(JrBase):
    name: Optional[Str200] = None
    date: Optional[PartialDate] = None
    issuer: Optional[Str200] = None
    url: Optional[HttpUrl] = None


class JrPublication(JrBase):
    name: Optional[Str300] = None
    publisher: Optional[Str200] = None
    release_date: Optional[PartialDate] = Field(None, alias="releaseDate")
    url: Optional[HttpUrl] = None
    summary: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None


class JrSkill(JrBase):
    name: Optional[Str200] = None
    level: Optional[str] = Field(None, max_length=60)
    keywords: Optional[list[Str200]] = None


class JrLanguage(JrBase):
    language: Optional[str] = Field(None, max_length=80)
    fluency: Optional[str] = Field(None, max_length=80)


class JrInterest(JrBase):
    name: Optional[Str200] = None
    keywords: Optional[list[Str200]] = None


class JrReference(JrBase):
    name: Optional[Str200] = None
    reference: Optional[Annotated[str, StringConstraints(max_length=3000)]] = None


class JrProject(JrBase):
    name: Optional[Str200] = None
    description: Optional[Annotated[str, StringConstraints(max_length=5000)]] = None
    highlights: Optional[list[Str300]] = None
    keywords: Optional[list[Str200]] = None
    start_date: Optional[PartialDate] = Field(None, alias="startDate")
    end_date: Optional[PartialDate] = Field(None, alias="endDate")
    url: Optional[HttpUrl] = None
    roles: Optional[list[Str200]] = None
    entity: Optional[Str200] = None
    type: Optional[str] = Field(None, max_length=100)


class JrMeta(JrBase):
    canonical: Optional[HttpUrl] = None
    version: Optional[str] = Field(None, max_length=20)
    last_modified: Optional[str] = Field(None, alias="lastModified", max_length=40)


class JsonResume(JrBase):
    """Full json-resume document — the canonical stored shape of every resume."""

    basics: Optional[JrBasics] = None
    work: Optional[list[JrWork]] = None
    volunteer: Optional[list[JrVolunteer]] = None
    education: Optional[list[JrEducation]] = None
    awards: Optional[list[JrAward]] = None
    certificates: Optional[list[JrCertificate]] = None
    publications: Optional[list[JrPublication]] = None
    skills: Optional[list[JrSkill]] = None
    languages: Optional[list[JrLanguage]] = None
    interests: Optional[list[JrInterest]] = None
    references: Optional[list[JrReference]] = None
    projects: Optional[list[JrProject]] = None
    meta: Optional[JrMeta] = None

# =============================================================================
# Base document with timestamps + optimistic locking
# =============================================================================


class TimestampedDocument(Document):
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    schema_version: int = 1

    @before_event(Replace, SaveChanges)
    def _touch(self) -> None:
        self.updated_at = utcnow()


# =============================================================================
# users
# =============================================================================


class OAuthIdentity(BaseModel):
    provider: OAuthProvider
    provider_user_id: Str300
    email: Optional[EmailStr] = None
    linked_at: datetime = Field(default_factory=utcnow)


class User(TimestampedDocument):
    email: EmailStr
    # bcrypt/argon2 hash; absent for OAuth-only accounts. Excluded from API output.
    password_hash: Optional[str] = Field(None, exclude=True)
    full_name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    avatar_url: Optional[HttpUrl] = None

    # RBAC — backend-controlled. There is NO separate admin registration flow.
    role: UserRole = UserRole.CANDIDATE
    status: UserStatus = UserStatus.ACTIVE

    oauth_identities: list[OAuthIdentity] = Field(default_factory=list)
    email_verified: bool = False

    last_active_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[PydanticObjectId] = None

    # Denormalized counters for dashboards / admin user list (kept in sync transactionally).
    resume_count: int = Field(0, ge=0)
    analysis_count: int = Field(0, ge=0)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.lower().strip()

    class Settings:
        name = "users"
        use_revision = True  # optimistic locking
        use_state_management = True
        indexes = [
            # Unique, case-insensitive email.
            IndexModel(
                [("email", pymongo.ASCENDING)],
                name="uniq_email_ci",
                unique=True,
                collation={"locale": "en", "strength": 2},
            ),
            # One account per OAuth identity.
            IndexModel(
                [
                    ("oauth_identities.provider", pymongo.ASCENDING),
                    ("oauth_identities.provider_user_id", pymongo.ASCENDING),
                ],
                name="uniq_oauth_identity",
                unique=True,
                partialFilterExpression={"oauth_identities.0": {"$exists": True}},
            ),
            # Admin user search + listings.
            IndexModel(
                [("full_name", pymongo.TEXT), ("email", pymongo.TEXT)],
                name="txt_user_search",
            ),
            IndexModel([("created_at", pymongo.DESCENDING)], name="created_desc"),
            IndexModel(
                [("status", pymongo.ASCENDING), ("last_active_at", pymongo.DESCENDING)],
                name="status_active",
            ),
            IndexModel([("role", pymongo.ASCENDING)], name="role"),
        ]


# =============================================================================
# resumes
# =============================================================================


class OriginalFile(BaseModel):
    file_name: Str300
    mime_type: str
    size_bytes: int = Field(..., ge=1, le=MAX_RESUME_FILE_BYTES)
    # Object-storage key (S3/GCS) — raw bytes never live in MongoDB.
    storage_key: str
    sha256: Optional[str] = Field(None, max_length=64)  # dedupe / integrity

    @field_validator("mime_type")
    @classmethod
    def _allowed_mime(cls, v: str) -> str:
        if v not in ALLOWED_RESUME_MIME:
            raise ValueError("Only .pdf, .doc and .docx files are allowed")
        return v


class UploadParse(BaseModel):
    status: UploadParseStatus = UploadParseStatus.PENDING
    model_used: Optional[str] = None  # e.g. "anthropic/claude-haiku-4-5"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None


class Resume(TimestampedDocument):
    user_id: PydanticObjectId
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    source: ResumeSource

    # Canonical structured resume — json-resume-schema.
    json_resume: JsonResume

    # Upload-flow fields (source == UPLOADED)
    original_file: Optional[OriginalFile] = None
    # Raw text extracted from the uploaded file — shown beside the edit form.
    original_text: Optional[Annotated[str, StringConstraints(max_length=200_000)]] = None
    upload_parse: Optional[UploadParse] = None

    # Analysis rollup for the dashboard table.
    analysis_status: ResumeAnalysisStatus = ResumeAnalysisStatus.UNANALYZED
    last_analyzed_at: Optional[datetime] = None
    analysis_count: int = Field(0, ge=0)

    # Soft delete.
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[PydanticObjectId] = None  # user or admin

    @model_validator(mode="after")
    def _strip_placeholders(self) -> "Resume":
        """Empty/placeholder fields are NEVER persisted (PROMPT.md requirement)."""
        pruned = _prune(self.json_resume.model_dump(exclude_none=True, by_alias=True)) or {}
        object.__setattr__(self, "json_resume", JsonResume.model_validate(pruned))
        return self

    @model_validator(mode="after")
    def _uploaded_needs_file(self) -> "Resume":
        if self.source == ResumeSource.UPLOADED and self.original_file is None:
            raise ValueError("Uploaded resumes must reference the original file")
        return self

    class Settings:
        name = "resumes"
        use_revision = True
        use_state_management = True
        indexes = [
            # Dashboard listing: a user's live resumes, newest first.
            IndexModel(
                [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="user_live_resumes",
                partialFilterExpression={"deleted_at": None},
            ),
            # Resume name unique per user (live docs only).
            IndexModel(
                [("user_id", pymongo.ASCENDING), ("name", pymongo.ASCENDING)],
                name="uniq_user_resume_name",
                unique=True,
                collation={"locale": "en", "strength": 2},
                partialFilterExpression={"deleted_at": None},
            ),
            IndexModel(
                [("analysis_status", pymongo.ASCENDING), ("updated_at", pymongo.DESCENDING)],
                name="analysis_status",
            ),
        ]


# =============================================================================
# analyses
# =============================================================================


class AnalysisStep(BaseModel):
    key: AnalysisStepKey
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None


def _default_steps() -> list[AnalysisStep]:
    return [AnalysisStep(key=k) for k in AnalysisStepKey]


class Suggestion(BaseModel):
    suggestion_id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    group: SuggestionGroup
    # json-resume field path the suggestion targets, e.g. "work[0].highlights".
    field_ref: Str200
    title: Str300
    description: Annotated[str, StringConstraints(min_length=1, max_length=5000)]
    # Concrete replacement / addition the UI can apply with one click.
    proposed_value: Optional[LongText] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    dismissed: bool = False


class InterviewQuestion(BaseModel):
    question: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    suggested_answer: LongText


class AnalysisResult(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    ats_score: int = Field(..., ge=0, le=100)
    project_score: Optional[int] = Field(None, ge=0, le=100)
    strong_points: list[Str300] = Field(default_factory=list)
    weak_points: list[Str300] = Field(default_factory=list)
    matching_skills: list[Str200] = Field(default_factory=list)
    skill_gaps: list[Str200] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)


class Analysis(TimestampedDocument):
    user_id: PydanticObjectId
    resume_id: PydanticObjectId
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    job_description: Annotated[str, StringConstraints(min_length=30, max_length=50_000)]

    # Immutable snapshot of the resume at analysis time (resume may be edited later).
    resume_snapshot: JsonResume

    status: AnalysisStatus = AnalysisStatus.PENDING
    # Fixed 3-step pipeline, mirrored in the progress UI.
    steps: list[AnalysisStep] = Field(default_factory=_default_steps)

    result: Optional[AnalysisResult] = None

    model_used: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(None, ge=0)
    error: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None
    retry_count: int = Field(0, ge=0, le=5)

    @field_validator("steps")
    @classmethod
    def _exactly_three_steps(cls, v: list[AnalysisStep]) -> list[AnalysisStep]:
        if len(v) != 3:
            raise ValueError("Analysis must have exactly 3 steps")
        return v

    @model_validator(mode="after")
    def _completed_has_result(self) -> "Analysis":
        if self.status == AnalysisStatus.COMPLETED and self.result is None:
            raise ValueError("Completed analysis must carry a result")
        return self

    class Settings:
        name = "analyses"
        use_revision = True
        use_state_management = True
        indexes = [
            IndexModel(
                [("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="user_analyses",
            ),
            IndexModel(
                [("resume_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="resume_analyses",
            ),
            # Worker queue scan: pending/in-progress jobs, oldest first.
            IndexModel(
                [("status", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)],
                name="job_queue",
                partialFilterExpression={"status": {"$in": ["pending", "in_progress"]}},
            ),
        ]


# =============================================================================
# notifications
# =============================================================================


class Notification(Document):
    user_id: PydanticObjectId
    type: NotificationType
    analysis_id: PydanticObjectId
    title: Str300
    body: Optional[Annotated[str, StringConstraints(max_length=500)]] = None

    state: NotificationState = NotificationState.ACTIVE
    # Cleared when user visits the analysis details page or clears manually.
    cleared_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utcnow)
    # Hard TTL — notifications expire 30 days after creation.
    expires_at: datetime = Field(default_factory=lambda: utcnow() + timedelta(days=30))

    class Settings:
        name = "notifications"
        indexes = [
            # Bell dropdown: a user's active notifications, newest first.
            IndexModel(
                [
                    ("user_id", pymongo.ASCENDING),
                    ("state", pymongo.ASCENDING),
                    ("created_at", pymongo.DESCENDING),
                ],
                name="user_active_notifs",
                partialFilterExpression={"state": "active"},
            ),
            # One ACTIVE notification per analysis (progress -> completed replaces in place).
            IndexModel(
                [("analysis_id", pymongo.ASCENDING)],
                name="uniq_active_per_analysis",
                unique=True,
                partialFilterExpression={"state": "active"},
            ),
            IndexModel([("expires_at", pymongo.ASCENDING)], name="ttl", expireAfterSeconds=0),
        ]


# =============================================================================
# aimodels (admin settings)
# =============================================================================


class AiModel(TimestampedDocument):
    model_config = ConfigDict(protected_namespaces=())  # allow "model_name"

    model_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    provider: Annotated[str, StringConstraints(min_length=1, max_length=80)]

    # AES-256-GCM ciphertext (KMS-managed data key). NEVER the raw key. Never serialized.
    api_key_encrypted: str = Field(..., exclude=True)
    # Last 4 chars for the masked admin UI ("sk-ant-****3kF9").
    api_key_last4: Annotated[str, StringConstraints(min_length=2, max_length=8)]

    usages: list[AiModelUsage] = Field(default_factory=lambda: [AiModelUsage.ANALYSIS])
    status: AiModelStatus = AiModelStatus.ACTIVE

    added_by: PydanticObjectId
    last_used_at: Optional[datetime] = None

    class Settings:
        name = "aimodels"
        indexes = [
            IndexModel(
                [("provider", pymongo.ASCENDING), ("model_name", pymongo.ASCENDING)],
                name="uniq_provider_model",
                unique=True,
                collation={"locale": "en", "strength": 2},
            ),
            IndexModel(
                [("status", pymongo.ASCENDING), ("usages", pymongo.ASCENDING)],
                name="active_by_usage",
            ),
        ]


# =============================================================================
# authtokens — refresh / password-reset / email-verify (TTL)
# =============================================================================


class AuthToken(Document):
    user_id: PydanticObjectId
    kind: TokenKind
    # SHA-256 of the opaque token — the raw token is never stored. Never serialized.
    token_hash: str = Field(..., exclude=True)

    expires_at: datetime
    consumed_at: Optional[datetime] = None

    # Session forensics (refresh tokens).
    ip: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=400)

    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "authtokens"
        indexes = [
            IndexModel([("token_hash", pymongo.ASCENDING)], name="uniq_token", unique=True),
            IndexModel(
                [("user_id", pymongo.ASCENDING), ("kind", pymongo.ASCENDING)],
                name="user_tokens",
            ),
            IndexModel([("expires_at", pymongo.ASCENDING)], name="ttl", expireAfterSeconds=0),
        ]


# =============================================================================
# auditlogs — admin & security-relevant actions
# =============================================================================


class AuditLog(Document):
    actor_id: PydanticObjectId
    action: AuditAction
    target_type: Optional[str] = Field(None, max_length=40)  # 'user' | 'resume' | 'aimodel'
    target_id: Optional[PydanticObjectId] = None
    # Redacted diff / context — never secrets or resume content.
    meta: Optional[dict[str, Any]] = None
    ip: Optional[str] = Field(None, max_length=45)
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "auditlogs"
        indexes = [
            IndexModel(
                [("actor_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
                name="actor_history",
            ),
            IndexModel(
                [
                    ("target_type", pymongo.ASCENDING),
                    ("target_id", pymongo.ASCENDING),
                    ("created_at", pymongo.DESCENDING),
                ],
                name="target_history",
            ),
            # Retain 400 days.
            IndexModel(
                [("created_at", pymongo.ASCENDING)],
                name="ttl",
                expireAfterSeconds=400 * 24 * 3600,
            ),
        ]


# =============================================================================
# init_beanie registration list
# =============================================================================

DOCUMENT_MODELS: list[type[Document]] = [
    User,
    Resume,
    Analysis,
    Notification,
    AiModel,
    AuthToken,
    AuditLog,
]

