/**
 * json-resume form model (issue #77). Mirrors the server JsonResume by-alias
 * shape (camelCase: startDate/endDate/studyType/releaseDate/postalCode/
 * countryCode/lastModified). Every field is optional and string-typed for the
 * form; `pruneEmpty` strips placeholders before submit (mirror of the server's
 * recursive prune so placeholders are NEVER persisted).
 */

export interface JrProfile {
  network: string;
  username: string;
  url: string;
}
export interface JrLocation {
  address: string;
  postalCode: string;
  city: string;
  countryCode: string;
  region: string;
}
export interface JrBasics {
  name: string;
  label: string;
  email: string;
  phone: string;
  url: string;
  image: string;
  summary: string;
  location: JrLocation;
  profiles: JrProfile[];
}
export interface JrWork {
  name: string;
  position: string;
  location: string;
  url: string;
  startDate: string;
  endDate: string;
  summary: string;
  highlights: { value: string }[];
}
export interface JrVolunteer {
  organization: string;
  position: string;
  url: string;
  startDate: string;
  endDate: string;
  summary: string;
}
export interface JrEducation {
  institution: string;
  area: string;
  studyType: string;
  url: string;
  startDate: string;
  endDate: string;
  score: string;
}
export interface JrAward {
  title: string;
  date: string;
  awarder: string;
  summary: string;
}
export interface JrCertificate {
  name: string;
  date: string;
  issuer: string;
  url: string;
}
export interface JrPublication {
  name: string;
  publisher: string;
  releaseDate: string;
  url: string;
  summary: string;
}
export interface JrSkill {
  name: string;
  level: string;
  keywords: { value: string }[];
}
export interface JrLanguage {
  language: string;
  fluency: string;
}
export interface JrInterest {
  name: string;
  keywords: { value: string }[];
}
export interface JrReference {
  name: string;
  reference: string;
}
export interface JrProject {
  name: string;
  description: string;
  url: string;
  entity: string;
  type: string;
  startDate: string;
  endDate: string;
  highlights: { value: string }[];
}
export interface JrMeta {
  canonical: string;
  version: string;
  lastModified: string;
}

export interface ResumeForm {
  name: string; // resume document name (not part of json-resume)
  basics: JrBasics;
  work: JrWork[];
  volunteer: JrVolunteer[];
  education: JrEducation[];
  awards: JrAward[];
  certificates: JrCertificate[];
  publications: JrPublication[];
  skills: JrSkill[];
  languages: JrLanguage[];
  interests: JrInterest[];
  references: JrReference[];
  projects: JrProject[];
  meta: JrMeta;
}

export const emptyLocation = (): JrLocation => ({
  address: "",
  postalCode: "",
  city: "",
  countryCode: "",
  region: "",
});
export const emptyProfile = (): JrProfile => ({ network: "", username: "", url: "" });
export const emptyWork = (): JrWork => ({
  name: "",
  position: "",
  location: "",
  url: "",
  startDate: "",
  endDate: "",
  summary: "",
  highlights: [],
});
export const emptyVolunteer = (): JrVolunteer => ({
  organization: "",
  position: "",
  url: "",
  startDate: "",
  endDate: "",
  summary: "",
});
export const emptyEducation = (): JrEducation => ({
  institution: "",
  area: "",
  studyType: "",
  url: "",
  startDate: "",
  endDate: "",
  score: "",
});
export const emptyAward = (): JrAward => ({ title: "", date: "", awarder: "", summary: "" });
export const emptyCertificate = (): JrCertificate => ({ name: "", date: "", issuer: "", url: "" });
export const emptyPublication = (): JrPublication => ({
  name: "",
  publisher: "",
  releaseDate: "",
  url: "",
  summary: "",
});
export const emptySkill = (): JrSkill => ({ name: "", level: "", keywords: [] });
export const emptyLanguage = (): JrLanguage => ({ language: "", fluency: "" });
export const emptyInterest = (): JrInterest => ({ name: "", keywords: [] });
export const emptyReference = (): JrReference => ({ name: "", reference: "" });
export const emptyProject = (): JrProject => ({
  name: "",
  description: "",
  url: "",
  entity: "",
  type: "",
  startDate: "",
  endDate: "",
  highlights: [],
});
export const emptyKeyword = () => ({ value: "" });

export function emptyResumeForm(name = ""): ResumeForm {
  return {
    name,
    basics: {
      name: "",
      label: "",
      email: "",
      phone: "",
      url: "",
      image: "",
      summary: "",
      location: emptyLocation(),
      profiles: [],
    },
    work: [],
    volunteer: [],
    education: [],
    awards: [],
    certificates: [],
    publications: [],
    skills: [],
    languages: [],
    interests: [],
    references: [],
    projects: [],
    meta: { canonical: "", version: "", lastModified: "" },
  };
}

/** Recursively drop empty strings / arrays / objects (mirror of the server prune). */
export function pruneEmpty(value: unknown): unknown {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed === "" ? undefined : trimmed;
  }
  if (Array.isArray(value)) {
    const items = value.map(pruneEmpty).filter((v) => v !== undefined);
    return items.length ? items : undefined;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      const pruned = pruneEmpty(val);
      if (pruned !== undefined) out[key] = pruned;
    }
    return Object.keys(out).length ? out : undefined;
  }
  return value ?? undefined;
}

/** Flatten `{value}` keyword/highlight wrappers into plain string arrays. */
function unwrapValues(list: { value: string }[] | undefined): string[] {
  return (list ?? []).map((x) => x.value);
}

/** Build the json-resume payload (camelCase, pruned) the API expects. */
export function toJsonResume(form: ResumeForm): Record<string, unknown> {
  const shaped = {
    basics: {
      ...form.basics,
      profiles: form.basics.profiles,
    },
    work: form.work.map((w) => ({ ...w, highlights: unwrapValues(w.highlights) })),
    volunteer: form.volunteer,
    education: form.education,
    awards: form.awards,
    certificates: form.certificates,
    publications: form.publications,
    skills: form.skills.map((s) => ({ ...s, keywords: unwrapValues(s.keywords) })),
    languages: form.languages,
    interests: form.interests.map((i) => ({ ...i, keywords: unwrapValues(i.keywords) })),
    references: form.references,
    projects: form.projects.map((p) => ({ ...p, highlights: unwrapValues(p.highlights) })),
    meta: form.meta,
  };
  return (pruneEmpty(shaped) as Record<string, unknown>) ?? {};
}
