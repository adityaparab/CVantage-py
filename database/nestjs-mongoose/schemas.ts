/**
 * CVantage — MongoDB schema (NestJS + @nestjs/mongoose / Mongoose 8)
 * =================================================================
 * Production-grade data model for the resume-analysis platform described in PROMPT.md.
 *
 * Collections
 *  - users           : candidates + admins (role decided by backend RBAC, single login flow)
 *  - resumes         : created or uploaded resumes, stored as json-resume-schema
 *  - analyses        : JD-vs-resume analysis jobs, 3-step pipeline + results
 *  - notifications   : in-app bell notifications (analysis progress / completion)
 *  - aimodels        : admin-managed AI model registry (encrypted API keys)
 *  - authtokens      : refresh / password-reset / email-verify tokens (TTL)
 *  - auditlogs       : admin & security-relevant actions (TTL 400 days)
 *
 * Conventions
 *  - timestamps: true everywhere (createdAt / updatedAt)
 *  - optimisticConcurrency: true on mutable aggregates (resumes, analyses, users)
 *  - soft delete via deletedAt (partial indexes exclude soft-deleted docs)
 *  - json-resume dates kept as partial-date STRINGS ("2024", "2024-03", "2024-03-01")
 *    exactly as the json-resume-schema specifies — never coerced to Date
 *  - empty/placeholder fields are stripped before save (see Resume pre-validate hook);
 *    placeholders are NEVER persisted
 *  - secrets (passwordHash, apiKeyEncrypted, tokenHash) are select:false
 */

import { Prop, PropOptions, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument, Schema as MongooseSchema, Types } from 'mongoose';

/* ============================================================================
 * Shared enums & helpers
 * ========================================================================== */

export enum UserRole {
  CANDIDATE = 'candidate',
  ADMIN = 'admin',
}

export enum UserStatus {
  ACTIVE = 'active',
  DEACTIVATED = 'deactivated',
}

export enum OAuthProvider {
  GOOGLE = 'google',
  LINKEDIN = 'linkedin',
}

export enum ResumeSource {
  CREATED = 'created', // built with the in-app form
  UPLOADED = 'uploaded', // file upload → AI-parsed
}

export enum ResumeAnalysisStatus {
  UNANALYZED = 'unanalyzed',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum UploadParseStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum AnalysisStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum AnalysisStepKey {
  COMPARE = 'compare_resume_jd',
  SUGGESTIONS = 'generate_suggestions',
  INTERVIEW_QUESTIONS = 'prepare_interview_questions',
}

export enum StepStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum NotificationType {
  ANALYSIS_IN_PROGRESS = 'analysis_in_progress',
  ANALYSIS_COMPLETED = 'analysis_completed',
  ANALYSIS_FAILED = 'analysis_failed',
}

export enum NotificationState {
  ACTIVE = 'active', // shown in the bell
  CLEARED = 'cleared', // visited details page or cleared manually
}

export enum AiModelUsage {
  RESUME_PARSING = 'resume_parsing',
  ANALYSIS = 'analysis',
  FALLBACK = 'fallback',
}

export enum AiModelStatus {
  ACTIVE = 'active',
  DISABLED = 'disabled',
}

export enum TokenKind {
  REFRESH = 'refresh',
  PASSWORD_RESET = 'password_reset',
  EMAIL_VERIFY = 'email_verify',
}

export enum SuggestionGroup {
  ATS = 'ats_improvement',
  SKILL_EMPHASIS = 'skill_emphasis',
  WORDING = 'wording',
  SKILL_ADDITION = 'skill_addition',
  PROJECT = 'project',
}

/** json-resume partial date: "YYYY" | "YYYY-MM" | "YYYY-MM-DD" */
export const JSON_RESUME_DATE = /^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\/.+/i;

const dateProp: PropOptions<string> = {
  type: String,
  match: [JSON_RESUME_DATE, 'Date must be YYYY, YYYY-MM or YYYY-MM-DD'],
  trim: true,
};

const ALLOWED_RESUME_MIME = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

/* ============================================================================
 * json-resume-schema subdocuments (https://jsonresume.org/schema)
 * All fields optional — empty values are stripped pre-validate, never stored.
 * ========================================================================== */

@Schema({ _id: false })
export class JrLocation {
  @Prop({ trim: true, maxlength: 300 }) address?: string;
  @Prop({ trim: true, maxlength: 20 }) postalCode?: string;
  @Prop({ trim: true, maxlength: 120 }) city?: string;
  @Prop({ trim: true, uppercase: true, minlength: 2, maxlength: 2 }) countryCode?: string;
  @Prop({ trim: true, maxlength: 120 }) region?: string;
}
const JrLocationSchema = SchemaFactory.createForClass(JrLocation);

@Schema({ _id: false })
export class JrProfile {
  @Prop({ trim: true, maxlength: 60 }) network?: string;
  @Prop({ trim: true, maxlength: 120 }) username?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
}
const JrProfileSchema = SchemaFactory.createForClass(JrProfile);

@Schema({ _id: false })
export class JrBasics {
  @Prop({ trim: true, maxlength: 200 }) name?: string;
  @Prop({ trim: true, maxlength: 200 }) label?: string;
  @Prop({ trim: true, match: URL_RE }) image?: string;
  @Prop({ trim: true, lowercase: true, match: EMAIL_RE }) email?: string;
  @Prop({ trim: true, maxlength: 40 }) phone?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop({ trim: true, maxlength: 5000 }) summary?: string;
  @Prop({ type: JrLocationSchema }) location?: JrLocation;
  @Prop({ type: [JrProfileSchema], default: undefined }) profiles?: JrProfile[];
}
const JrBasicsSchema = SchemaFactory.createForClass(JrBasics);

@Schema({ _id: false })
export class JrWork {
  @Prop({ trim: true, maxlength: 200 }) name?: string; // company
  @Prop({ trim: true, maxlength: 200 }) location?: string;
  @Prop({ trim: true, maxlength: 1000 }) description?: string;
  @Prop({ trim: true, maxlength: 200 }) position?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop(dateProp) startDate?: string;
  @Prop(dateProp) endDate?: string;
  @Prop({ trim: true, maxlength: 5000 }) summary?: string;
  @Prop({ type: [String], default: undefined }) highlights?: string[];
}
const JrWorkSchema = SchemaFactory.createForClass(JrWork);

@Schema({ _id: false })
export class JrVolunteer {
  @Prop({ trim: true, maxlength: 200 }) organization?: string;
  @Prop({ trim: true, maxlength: 200 }) position?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop(dateProp) startDate?: string;
  @Prop(dateProp) endDate?: string;
  @Prop({ trim: true, maxlength: 5000 }) summary?: string;
  @Prop({ type: [String], default: undefined }) highlights?: string[];
}
const JrVolunteerSchema = SchemaFactory.createForClass(JrVolunteer);

@Schema({ _id: false })
export class JrEducation {
  @Prop({ trim: true, maxlength: 200 }) institution?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop({ trim: true, maxlength: 200 }) area?: string;
  @Prop({ trim: true, maxlength: 100 }) studyType?: string;
  @Prop(dateProp) startDate?: string;
  @Prop(dateProp) endDate?: string;
  @Prop({ trim: true, maxlength: 50 }) score?: string;
  @Prop({ type: [String], default: undefined }) courses?: string[];
}
const JrEducationSchema = SchemaFactory.createForClass(JrEducation);

@Schema({ _id: false })
export class JrAward {
  @Prop({ trim: true, maxlength: 200 }) title?: string;
  @Prop(dateProp) date?: string;
  @Prop({ trim: true, maxlength: 200 }) awarder?: string;
  @Prop({ trim: true, maxlength: 2000 }) summary?: string;
}
const JrAwardSchema = SchemaFactory.createForClass(JrAward);

@Schema({ _id: false })
export class JrCertificate {
  @Prop({ trim: true, maxlength: 200 }) name?: string;
  @Prop(dateProp) date?: string;
  @Prop({ trim: true, maxlength: 200 }) issuer?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
}
const JrCertificateSchema = SchemaFactory.createForClass(JrCertificate);

@Schema({ _id: false })
export class JrPublication {
  @Prop({ trim: true, maxlength: 300 }) name?: string;
  @Prop({ trim: true, maxlength: 200 }) publisher?: string;
  @Prop(dateProp) releaseDate?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop({ trim: true, maxlength: 2000 }) summary?: string;
}
const JrPublicationSchema = SchemaFactory.createForClass(JrPublication);

@Schema({ _id: false })
export class JrSkill {
  @Prop({ trim: true, maxlength: 120 }) name?: string;
  @Prop({ trim: true, maxlength: 60 }) level?: string;
  @Prop({ type: [String], default: undefined }) keywords?: string[];
}
const JrSkillSchema = SchemaFactory.createForClass(JrSkill);

@Schema({ _id: false })
export class JrLanguage {
  @Prop({ trim: true, maxlength: 80 }) language?: string;
  @Prop({ trim: true, maxlength: 80 }) fluency?: string;
}
const JrLanguageSchema = SchemaFactory.createForClass(JrLanguage);

@Schema({ _id: false })
export class JrInterest {
  @Prop({ trim: true, maxlength: 120 }) name?: string;
  @Prop({ type: [String], default: undefined }) keywords?: string[];
}
const JrInterestSchema = SchemaFactory.createForClass(JrInterest);

@Schema({ _id: false })
export class JrReference {
  @Prop({ trim: true, maxlength: 200 }) name?: string;
  @Prop({ trim: true, maxlength: 3000 }) reference?: string;
}
const JrReferenceSchema = SchemaFactory.createForClass(JrReference);

@Schema({ _id: false })
export class JrProject {
  @Prop({ trim: true, maxlength: 200 }) name?: string;
  @Prop({ trim: true, maxlength: 5000 }) description?: string;
  @Prop({ type: [String], default: undefined }) highlights?: string[];
  @Prop({ type: [String], default: undefined }) keywords?: string[];
  @Prop(dateProp) startDate?: string;
  @Prop(dateProp) endDate?: string;
  @Prop({ trim: true, match: URL_RE }) url?: string;
  @Prop({ type: [String], default: undefined }) roles?: string[];
  @Prop({ trim: true, maxlength: 200 }) entity?: string;
  @Prop({ trim: true, maxlength: 100 }) type?: string;
}
const JrProjectSchema = SchemaFactory.createForClass(JrProject);

@Schema({ _id: false })
export class JrMeta {
  @Prop({ trim: true, match: URL_RE }) canonical?: string;
  @Prop({ trim: true, maxlength: 20 }) version?: string;
  @Prop({ trim: true, maxlength: 40 }) lastModified?: string;
}
const JrMetaSchema = SchemaFactory.createForClass(JrMeta);

/** Full json-resume document — the canonical stored shape of every resume. */
@Schema({ _id: false })
export class JsonResume {
  @Prop({ type: JrBasicsSchema }) basics?: JrBasics;
  @Prop({ type: [JrWorkSchema], default: undefined }) work?: JrWork[];
  @Prop({ type: [JrVolunteerSchema], default: undefined }) volunteer?: JrVolunteer[];
  @Prop({ type: [JrEducationSchema], default: undefined }) education?: JrEducation[];
  @Prop({ type: [JrAwardSchema], default: undefined }) awards?: JrAward[];
  @Prop({ type: [JrCertificateSchema], default: undefined }) certificates?: JrCertificate[];
  @Prop({ type: [JrPublicationSchema], default: undefined }) publications?: JrPublication[];
  @Prop({ type: [JrSkillSchema], default: undefined }) skills?: JrSkill[];
  @Prop({ type: [JrLanguageSchema], default: undefined }) languages?: JrLanguage[];
  @Prop({ type: [JrInterestSchema], default: undefined }) interests?: JrInterest[];
  @Prop({ type: [JrReferenceSchema], default: undefined }) references?: JrReference[];
  @Prop({ type: [JrProjectSchema], default: undefined }) projects?: JrProject[];
  @Prop({ type: JrMetaSchema }) meta?: JrMeta;
}
const JsonResumeSchema = SchemaFactory.createForClass(JsonResume);

/* ============================================================================
 * users
 * ========================================================================== */

@Schema({ _id: false })
export class OAuthIdentity {
  @Prop({ type: String, enum: OAuthProvider, required: true }) provider!: OAuthProvider;
  @Prop({ required: true, trim: true }) providerUserId!: string;
  @Prop({ trim: true, lowercase: true, match: EMAIL_RE }) email?: string;
  @Prop({ type: Date, default: () => new Date() }) linkedAt!: Date;
}
const OAuthIdentitySchema = SchemaFactory.createForClass(OAuthIdentity);

@Schema({
  collection: 'users',
  timestamps: true,
  optimisticConcurrency: true,
})
export class User {
  @Prop({
    required: true,
    trim: true,
    lowercase: true,
    match: [EMAIL_RE, 'Invalid email'],
    maxlength: 320,
  })
  email!: string;

  /** bcrypt/argon2 hash; absent for OAuth-only accounts. Never selected by default. */
  @Prop({ select: false }) passwordHash?: string;

  @Prop({ required: true, trim: true, minlength: 1, maxlength: 200 })
  fullName!: string;

  @Prop({ trim: true, match: URL_RE }) avatarUrl?: string;

  /** RBAC — backend-controlled. There is NO separate admin registration flow. */
  @Prop({ type: String, enum: UserRole, default: UserRole.CANDIDATE, index: true })
  role!: UserRole;

  @Prop({ type: String, enum: UserStatus, default: UserStatus.ACTIVE })
  status!: UserStatus;

  @Prop({ type: [OAuthIdentitySchema], default: [] })
  oauthIdentities!: OAuthIdentity[];

  @Prop({ default: false }) emailVerified!: boolean;

  @Prop({ type: Date }) lastActiveAt?: Date;
  @Prop({ type: Date }) deactivatedAt?: Date;
  @Prop({ type: Types.ObjectId, ref: 'User' }) deactivatedBy?: Types.ObjectId;

  /** Denormalized counters for dashboards / admin user list (kept in sync transactionally). */
  @Prop({ default: 0, min: 0 }) resumeCount!: number;
  @Prop({ default: 0, min: 0 }) analysisCount!: number;

  @Prop({ default: 1 }) schemaVersion!: number;
}
export type UserDocument = HydratedDocument<User>;
export const UserSchema = SchemaFactory.createForClass(User);

// Unique, case-insensitive email (collation strength 2).
UserSchema.index({ email: 1 }, { unique: true, collation: { locale: 'en', strength: 2 } });
// One account per OAuth identity. Partial → docs without identities are unaffected.
UserSchema.index(
  { 'oauthIdentities.provider': 1, 'oauthIdentities.providerUserId': 1 },
  { unique: true, partialFilterExpression: { 'oauthIdentities.0': { $exists: true } } },
);
// Admin user search (by name/email prefix) + sorting by registration date.
UserSchema.index({ fullName: 'text', email: 'text' });
UserSchema.index({ createdAt: -1 });
UserSchema.index({ status: 1, lastActiveAt: -1 });

UserSchema.set('toJSON', {
  versionKey: false,
  transform: (_doc: unknown, ret: any) => {
    delete ret.passwordHash;
    return ret;
  },
});

/* ============================================================================
 * resumes
 * ========================================================================== */

@Schema({ _id: false })
export class OriginalFile {
  @Prop({ required: true, trim: true, maxlength: 300 }) fileName!: string;
  @Prop({ type: String, enum: ALLOWED_RESUME_MIME, required: true }) mimeType!: string;
  @Prop({ required: true, min: 1, max: 10 * 1024 * 1024 }) sizeBytes!: number; // 10 MB cap
  /** Object-storage key (S3/GCS) — raw bytes never live in MongoDB. */
  @Prop({ required: true, trim: true }) storageKey!: string;
  @Prop({ trim: true, maxlength: 64 }) sha256?: string; // dedupe / integrity
}
const OriginalFileSchema = SchemaFactory.createForClass(OriginalFile);

@Schema({ _id: false })
export class UploadParse {
  @Prop({ type: String, enum: UploadParseStatus, default: UploadParseStatus.PENDING })
  status!: UploadParseStatus;
  @Prop({ trim: true }) modelUsed?: string; // e.g. "anthropic/claude-haiku-4-5"
  @Prop({ type: Date }) startedAt?: Date;
  @Prop({ type: Date }) completedAt?: Date;
  @Prop({ trim: true, maxlength: 2000 }) error?: string;
}
const UploadParseSchema = SchemaFactory.createForClass(UploadParse);

@Schema({
  collection: 'resumes',
  timestamps: true,
  optimisticConcurrency: true,
})
export class Resume {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true, index: true })
  userId!: Types.ObjectId;

  @Prop({ required: true, trim: true, minlength: 1, maxlength: 200 })
  name!: string;

  @Prop({ type: String, enum: ResumeSource, required: true })
  source!: ResumeSource;

  /** Canonical structured resume — json-resume-schema. */
  @Prop({ type: JsonResumeSchema, required: true })
  jsonResume!: JsonResume;

  /* Upload-flow fields (source === 'uploaded') */
  @Prop({ type: OriginalFileSchema }) originalFile?: OriginalFile;
  /** Raw text extracted from the uploaded file — shown beside the edit form. */
  @Prop({ maxlength: 200_000 }) originalText?: string;
  @Prop({ type: UploadParseSchema }) uploadParse?: UploadParse;

  /* Analysis rollup for the dashboard table */
  @Prop({
    type: String,
    enum: ResumeAnalysisStatus,
    default: ResumeAnalysisStatus.UNANALYZED,
  })
  analysisStatus!: ResumeAnalysisStatus;
  @Prop({ type: Date }) lastAnalyzedAt?: Date;
  @Prop({ default: 0, min: 0 }) analysisCount!: number;

  /* Soft delete */
  @Prop({ type: Date, default: null }) deletedAt?: Date | null;
  @Prop({ type: Types.ObjectId, ref: 'User' }) deletedBy?: Types.ObjectId; // user or admin

  @Prop({ default: 1 }) schemaVersion!: number;
}
export type ResumeDocument = HydratedDocument<Resume>;
export const ResumeSchema = SchemaFactory.createForClass(Resume);

// Dashboard listing: a user's live resumes, newest first.
ResumeSchema.index(
  { userId: 1, createdAt: -1 },
  { partialFilterExpression: { deletedAt: null } },
);
// Resume name unique per user (live docs only) — avoids confusing duplicate rows.
ResumeSchema.index(
  { userId: 1, name: 1 },
  {
    unique: true,
    collation: { locale: 'en', strength: 2 },
    partialFilterExpression: { deletedAt: null },
  },
);
ResumeSchema.index({ analysisStatus: 1, updatedAt: -1 });

/**
 * Placeholder hygiene: recursively strip empty strings, empty arrays/objects and
 * whitespace-only values from jsonResume so form placeholders are NEVER stored.
 */
function prune(value: unknown): unknown {
  if (typeof value === 'string') {
    const t = value.trim();
    return t.length ? t : undefined;
  }
  if (Array.isArray(value)) {
    const arr = value.map(prune).filter((v) => v !== undefined);
    return arr.length ? arr : undefined;
  }
  if (value !== null && typeof value === 'object' && !(value instanceof Date)) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const p = prune(v);
      if (p !== undefined) out[k] = p;
    }
    return Object.keys(out).length ? out : undefined;
  }
  return value;
}

ResumeSchema.pre('validate', function (this: ResumeDocument) {
  if (this.jsonResume) {
    const pruned = (prune(this.toObject().jsonResume) ?? {}) as JsonResume;
    this.jsonResume = pruned;
    this.markModified('jsonResume');
  }
});

/* ============================================================================
 * analyses
 * ========================================================================== */

@Schema({ _id: false })
export class AnalysisStep {
  @Prop({ type: String, enum: AnalysisStepKey, required: true }) key!: AnalysisStepKey;
  @Prop({ type: String, enum: StepStatus, default: StepStatus.PENDING }) status!: StepStatus;
  @Prop({ type: Date }) startedAt?: Date;
  @Prop({ type: Date }) completedAt?: Date;
  @Prop({ trim: true, maxlength: 2000 }) error?: string;
}
const AnalysisStepSchema = SchemaFactory.createForClass(AnalysisStep);

@Schema({ _id: true })
export class Suggestion {
  @Prop({ type: String, enum: SuggestionGroup, required: true }) group!: SuggestionGroup;
  /** json-resume field path the suggestion targets, e.g. "work[0].highlights". */
  @Prop({ required: true, trim: true, maxlength: 200 }) fieldRef!: string;
  @Prop({ required: true, trim: true, maxlength: 300 }) title!: string;
  @Prop({ required: true, trim: true, maxlength: 5000 }) description!: string;
  /** Concrete replacement / addition the UI can apply with one click. */
  @Prop({ trim: true, maxlength: 10_000 }) proposedValue?: string;
  @Prop({ default: false }) applied!: boolean;
  @Prop({ type: Date }) appliedAt?: Date;
  @Prop({ default: false }) dismissed!: boolean;
}
const SuggestionSchema = SchemaFactory.createForClass(Suggestion);

@Schema({ _id: false })
export class InterviewQuestion {
  @Prop({ required: true, trim: true, maxlength: 1000 }) question!: string;
  @Prop({ required: true, trim: true, maxlength: 10_000 }) suggestedAnswer!: string;
}
const InterviewQuestionSchema = SchemaFactory.createForClass(InterviewQuestion);

@Schema({ _id: false })
export class AnalysisResult {
  @Prop({ required: true, min: 0, max: 100 }) overallScore!: number;
  @Prop({ required: true, min: 0, max: 100 }) atsScore!: number;
  @Prop({ min: 0, max: 100 }) projectScore?: number;
  @Prop({ type: [String], default: [] }) strongPoints!: string[];
  @Prop({ type: [String], default: [] }) weakPoints!: string[];
  @Prop({ type: [String], default: [] }) matchingSkills!: string[];
  @Prop({ type: [String], default: [] }) skillGaps!: string[];
  @Prop({ type: [SuggestionSchema], default: [] }) suggestions!: Suggestion[];
  @Prop({ type: [InterviewQuestionSchema], default: [] })
  interviewQuestions!: InterviewQuestion[];
}
const AnalysisResultSchema = SchemaFactory.createForClass(AnalysisResult);

@Schema({
  collection: 'analyses',
  timestamps: true,
  optimisticConcurrency: true,
})
export class Analysis {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true, index: true })
  userId!: Types.ObjectId;

  @Prop({ type: Types.ObjectId, ref: 'Resume', required: true, index: true })
  resumeId!: Types.ObjectId;

  @Prop({ required: true, trim: true, minlength: 1, maxlength: 200 })
  name!: string;

  @Prop({ required: true, trim: true, minlength: 30, maxlength: 50_000 })
  jobDescription!: string;

  /** Immutable snapshot of the resume at analysis time (resume may be edited later). */
  @Prop({ type: JsonResumeSchema, required: true })
  resumeSnapshot!: JsonResume;

  @Prop({ type: String, enum: AnalysisStatus, default: AnalysisStatus.PENDING, index: true })
  status!: AnalysisStatus;

  /** Fixed 3-step pipeline, mirrored in the progress UI. */
  @Prop({
    type: [AnalysisStepSchema],
    default: () =>
      Object.values(AnalysisStepKey).map((key) => ({ key, status: StepStatus.PENDING })),
    validate: [(v: AnalysisStep[]) => v.length === 3, 'Analysis must have exactly 3 steps'],
  })
  steps!: AnalysisStep[];

  @Prop({ type: AnalysisResultSchema }) result?: AnalysisResult;

  @Prop({ trim: true }) modelUsed?: string;
  @Prop({ type: Date }) startedAt?: Date;
  @Prop({ type: Date }) completedAt?: Date;
  @Prop({ min: 0 }) durationMs?: number;
  @Prop({ trim: true, maxlength: 2000 }) error?: string;
  @Prop({ default: 0, min: 0, max: 5 }) retryCount!: number;

  @Prop({ default: 1 }) schemaVersion!: number;
}
export type AnalysisDocument = HydratedDocument<Analysis>;
export const AnalysisSchema = SchemaFactory.createForClass(Analysis);

AnalysisSchema.index({ userId: 1, createdAt: -1 });
AnalysisSchema.index({ resumeId: 1, createdAt: -1 });
// Worker queue scan: pending/in-progress jobs, oldest first.
AnalysisSchema.index(
  { status: 1, createdAt: 1 },
  {
    partialFilterExpression: {
      status: { $in: [AnalysisStatus.PENDING, AnalysisStatus.IN_PROGRESS] },
    },
  },
);

/* ============================================================================
 * notifications
 * ========================================================================== */

@Schema({ collection: 'notifications', timestamps: true })
export class Notification {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true, index: true })
  userId!: Types.ObjectId;

  @Prop({ type: String, enum: NotificationType, required: true })
  type!: NotificationType;

  @Prop({ type: Types.ObjectId, ref: 'Analysis', required: true })
  analysisId!: Types.ObjectId;

  @Prop({ required: true, trim: true, maxlength: 300 }) title!: string;
  @Prop({ trim: true, maxlength: 500 }) body?: string;

  @Prop({ type: String, enum: NotificationState, default: NotificationState.ACTIVE })
  state!: NotificationState;

  /** Cleared when user visits the analysis details page or clears manually. */
  @Prop({ type: Date }) clearedAt?: Date;

  /** Hard TTL — notifications expire 30 days after creation. */
  @Prop({ type: Date, default: () => new Date(Date.now() + 30 * 24 * 3600 * 1000) })
  expiresAt!: Date;
}
export type NotificationDocument = HydratedDocument<Notification>;
export const NotificationSchema = SchemaFactory.createForClass(Notification);

// Bell dropdown: a user's active notifications, newest first.
NotificationSchema.index(
  { userId: 1, state: 1, createdAt: -1 },
  { partialFilterExpression: { state: NotificationState.ACTIVE } },
);
// One ACTIVE notification per analysis (progress → completed replaces in place).
NotificationSchema.index(
  { analysisId: 1 },
  { unique: true, partialFilterExpression: { state: NotificationState.ACTIVE } },
);
NotificationSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

/* ============================================================================
 * aimodels (admin settings)
 * ========================================================================== */

@Schema({ collection: 'aimodels', timestamps: true })
export class AiModel {
  @Prop({ required: true, trim: true, maxlength: 120 }) modelName!: string;
  @Prop({ required: true, trim: true, maxlength: 80 }) provider!: string;

  /** AES-256-GCM ciphertext (KMS-managed data key). NEVER the raw key. */
  @Prop({ required: true, select: false }) apiKeyEncrypted!: string;
  /** Last 4 chars for the masked admin UI ("sk-ant-••••3kF9"). */
  @Prop({ required: true, minlength: 2, maxlength: 8 }) apiKeyLast4!: string;

  @Prop({ type: [String], enum: AiModelUsage, default: [AiModelUsage.ANALYSIS] })
  usages!: AiModelUsage[];

  @Prop({ type: String, enum: AiModelStatus, default: AiModelStatus.ACTIVE })
  status!: AiModelStatus;

  @Prop({ type: Types.ObjectId, ref: 'User', required: true }) addedBy!: Types.ObjectId;
  @Prop({ type: Date }) lastUsedAt?: Date;
}
export type AiModelDocument = HydratedDocument<AiModel>;
export const AiModelSchema = SchemaFactory.createForClass(AiModel);

AiModelSchema.index(
  { provider: 1, modelName: 1 },
  { unique: true, collation: { locale: 'en', strength: 2 } },
);
AiModelSchema.index({ status: 1, usages: 1 });

AiModelSchema.set('toJSON', {
  versionKey: false,
  transform: (_doc: unknown, ret: any) => {
    delete ret.apiKeyEncrypted;
    return ret;
  },
});

/* ============================================================================
 * authtokens — refresh / password-reset / email-verify (TTL)
 * ========================================================================== */

@Schema({ collection: 'authtokens', timestamps: true })
export class AuthToken {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true, index: true })
  userId!: Types.ObjectId;

  @Prop({ type: String, enum: TokenKind, required: true }) kind!: TokenKind;

  /** SHA-256 of the opaque token — the raw token is never stored. */
  @Prop({ required: true, select: false }) tokenHash!: string;

  @Prop({ type: Date, required: true }) expiresAt!: Date;
  @Prop({ type: Date }) consumedAt?: Date;

  /* Session forensics (refresh tokens) */
  @Prop({ trim: true, maxlength: 45 }) ip?: string;
  @Prop({ trim: true, maxlength: 400 }) userAgent?: string;
}
export type AuthTokenDocument = HydratedDocument<AuthToken>;
export const AuthTokenSchema = SchemaFactory.createForClass(AuthToken);

AuthTokenSchema.index({ tokenHash: 1 }, { unique: true });
AuthTokenSchema.index({ userId: 1, kind: 1 });
AuthTokenSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

/* ============================================================================
 * auditlogs — admin & security-relevant actions
 * ========================================================================== */

export enum AuditAction {
  USER_LOGIN = 'user.login',
  USER_REGISTER = 'user.register',
  ADMIN_USER_UPDATE = 'admin.user.update',
  ADMIN_USER_DEACTIVATE = 'admin.user.deactivate',
  ADMIN_PASSWORD_RESET = 'admin.user.password_reset',
  ADMIN_RESUME_DELETE = 'admin.resume.delete',
  ADMIN_MODEL_ADD = 'admin.model.add',
  ADMIN_MODEL_REMOVE = 'admin.model.remove',
  ADMIN_MODEL_KEY_ROTATE = 'admin.model.key_rotate',
  RESUME_DELETE = 'resume.delete',
}

@Schema({ collection: 'auditlogs', timestamps: { createdAt: true, updatedAt: false } })
export class AuditLog {
  @Prop({ type: Types.ObjectId, ref: 'User', required: true, index: true })
  actorId!: Types.ObjectId;

  @Prop({ type: String, enum: AuditAction, required: true }) action!: AuditAction;

  @Prop({ trim: true, maxlength: 40 }) targetType?: string; // 'user' | 'resume' | 'aimodel' …
  @Prop({ type: Types.ObjectId }) targetId?: Types.ObjectId;

  /** Redacted diff / context — never secrets or resume content. */
  @Prop({ type: MongooseSchema.Types.Mixed }) meta?: Record<string, unknown>;

  @Prop({ trim: true, maxlength: 45 }) ip?: string;

  createdAt?: Date;
}
export type AuditLogDocument = HydratedDocument<AuditLog>;
export const AuditLogSchema = SchemaFactory.createForClass(AuditLog);

AuditLogSchema.index({ actorId: 1, createdAt: -1 });
AuditLogSchema.index({ targetType: 1, targetId: 1, createdAt: -1 });
// Retain 400 days.
AuditLogSchema.index({ createdAt: 1 }, { expireAfterSeconds: 400 * 24 * 3600 });

/* ============================================================================
 * Module registration helper
 * ============================================================================
 * import { MongooseModule } from '@nestjs/mongoose';
 *
 * @Module({
 *   imports: [MongooseModule.forFeature(MODEL_DEFINITIONS)],
 * })
 * export class DatabaseModule {}
 */
export const MODEL_DEFINITIONS = [
  { name: User.name, schema: UserSchema },
  { name: Resume.name, schema: ResumeSchema },
  { name: Analysis.name, schema: AnalysisSchema },
  { name: Notification.name, schema: NotificationSchema },
  { name: AiModel.name, schema: AiModelSchema },
  { name: AuthToken.name, schema: AuthTokenSchema },
  { name: AuditLog.name, schema: AuditLogSchema },
];
