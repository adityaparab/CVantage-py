import { ArrayField, DateField, TextField, TextareaField } from "@/lib/forms";
import {
  emptyAward,
  emptyCertificate,
  emptyEducation,
  emptyInterest,
  emptyKeyword,
  emptyLanguage,
  emptyProfile,
  emptyProject,
  emptyPublication,
  emptyReference,
  emptySkill,
  emptyVolunteer,
  emptyWork,
  type ResumeForm,
} from "@/features/resume/jsonResume";

type Name = string;

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2">{children}</div>;
}

function StringList({ name, label, addLabel }: { name: Name; label: string; addLabel: string }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-text">{label}</p>
      <ArrayField<ResumeForm> name={name as never} newItem={emptyKeyword} addLabel={addLabel}>
        {(i) => <TextField<ResumeForm> name={`${name}.${i}.value` as never} label={`#${i + 1}`} />}
      </ArrayField>
    </div>
  );
}

export function BasicsSection() {
  return (
    <div className="flex flex-col gap-4">
      <Grid>
        <TextField<ResumeForm> name="basics.name" label="Full name" />
        <TextField<ResumeForm> name="basics.label" label="Headline" />
        <TextField<ResumeForm> name="basics.email" label="Email" type="email" />
        <TextField<ResumeForm> name="basics.phone" label="Phone" />
        <TextField<ResumeForm> name="basics.url" label="Website" />
        <TextField<ResumeForm> name="basics.image" label="Photo URL" />
      </Grid>
      <TextareaField<ResumeForm> name="basics.summary" label="Summary" rows={4} />
      <h3 className="text-sm font-semibold text-text">Location</h3>
      <Grid>
        <TextField<ResumeForm> name="basics.location.address" label="Address" />
        <TextField<ResumeForm> name="basics.location.city" label="City" />
        <TextField<ResumeForm> name="basics.location.region" label="Region" />
        <TextField<ResumeForm> name="basics.location.postalCode" label="Postal code" />
        <TextField<ResumeForm> name="basics.location.countryCode" label="Country code" />
      </Grid>
      <h3 className="text-sm font-semibold text-text">Profiles</h3>
      <ArrayField<ResumeForm> name="basics.profiles" newItem={emptyProfile} addLabel="Add profile">
        {(i) => (
          <Grid>
            <TextField<ResumeForm> name={`basics.profiles.${i}.network`} label="Network" />
            <TextField<ResumeForm> name={`basics.profiles.${i}.username`} label="Username" />
            <TextField<ResumeForm> name={`basics.profiles.${i}.url`} label="URL" />
          </Grid>
        )}
      </ArrayField>
    </div>
  );
}

export function WorkSection() {
  return (
    <ArrayField<ResumeForm> name="work" newItem={emptyWork} addLabel="Add work experience">
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`work.${i}.name`} label="Company" />
            <TextField<ResumeForm> name={`work.${i}.position`} label="Position" />
            <TextField<ResumeForm> name={`work.${i}.location`} label="Location" />
            <TextField<ResumeForm> name={`work.${i}.url`} label="URL" />
            <DateField<ResumeForm> name={`work.${i}.startDate`} label="Start date" />
            <DateField<ResumeForm> name={`work.${i}.endDate`} label="End date" />
          </Grid>
          <TextareaField<ResumeForm> name={`work.${i}.summary`} label="Summary" />
          <StringList name={`work.${i}.highlights`} label="Highlights" addLabel="Add highlight" />
        </div>
      )}
    </ArrayField>
  );
}

export function VolunteerSection() {
  return (
    <ArrayField<ResumeForm> name="volunteer" newItem={emptyVolunteer} addLabel="Add volunteering">
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`volunteer.${i}.organization`} label="Organization" />
            <TextField<ResumeForm> name={`volunteer.${i}.position`} label="Position" />
            <TextField<ResumeForm> name={`volunteer.${i}.url`} label="URL" />
            <DateField<ResumeForm> name={`volunteer.${i}.startDate`} label="Start date" />
            <DateField<ResumeForm> name={`volunteer.${i}.endDate`} label="End date" />
          </Grid>
          <TextareaField<ResumeForm> name={`volunteer.${i}.summary`} label="Summary" />
        </div>
      )}
    </ArrayField>
  );
}

export function EducationSection() {
  return (
    <ArrayField<ResumeForm> name="education" newItem={emptyEducation} addLabel="Add education">
      {(i) => (
        <Grid>
          <TextField<ResumeForm> name={`education.${i}.institution`} label="Institution" />
          <TextField<ResumeForm> name={`education.${i}.area`} label="Area of study" />
          <TextField<ResumeForm> name={`education.${i}.studyType`} label="Study type" />
          <TextField<ResumeForm> name={`education.${i}.score`} label="Score / GPA" />
          <DateField<ResumeForm> name={`education.${i}.startDate`} label="Start date" />
          <DateField<ResumeForm> name={`education.${i}.endDate`} label="End date" />
          <TextField<ResumeForm> name={`education.${i}.url`} label="URL" />
        </Grid>
      )}
    </ArrayField>
  );
}

export function AwardsSection() {
  return (
    <ArrayField<ResumeForm> name="awards" newItem={emptyAward} addLabel="Add award">
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`awards.${i}.title`} label="Title" />
            <TextField<ResumeForm> name={`awards.${i}.awarder`} label="Awarder" />
            <DateField<ResumeForm> name={`awards.${i}.date`} label="Date" />
          </Grid>
          <TextareaField<ResumeForm> name={`awards.${i}.summary`} label="Summary" />
        </div>
      )}
    </ArrayField>
  );
}

export function CertificatesSection() {
  return (
    <ArrayField<ResumeForm>
      name="certificates"
      newItem={emptyCertificate}
      addLabel="Add certificate"
    >
      {(i) => (
        <Grid>
          <TextField<ResumeForm> name={`certificates.${i}.name`} label="Name" />
          <TextField<ResumeForm> name={`certificates.${i}.issuer`} label="Issuer" />
          <DateField<ResumeForm> name={`certificates.${i}.date`} label="Date" />
          <TextField<ResumeForm> name={`certificates.${i}.url`} label="URL" />
        </Grid>
      )}
    </ArrayField>
  );
}

export function PublicationsSection() {
  return (
    <ArrayField<ResumeForm>
      name="publications"
      newItem={emptyPublication}
      addLabel="Add publication"
    >
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`publications.${i}.name`} label="Name" />
            <TextField<ResumeForm> name={`publications.${i}.publisher`} label="Publisher" />
            <DateField<ResumeForm> name={`publications.${i}.releaseDate`} label="Release date" />
            <TextField<ResumeForm> name={`publications.${i}.url`} label="URL" />
          </Grid>
          <TextareaField<ResumeForm> name={`publications.${i}.summary`} label="Summary" />
        </div>
      )}
    </ArrayField>
  );
}

export function SkillsSection() {
  return (
    <ArrayField<ResumeForm> name="skills" newItem={emptySkill} addLabel="Add skill">
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`skills.${i}.name`} label="Skill" />
            <TextField<ResumeForm> name={`skills.${i}.level`} label="Level" />
          </Grid>
          <StringList name={`skills.${i}.keywords`} label="Keywords" addLabel="Add keyword" />
        </div>
      )}
    </ArrayField>
  );
}

export function LanguagesSection() {
  return (
    <ArrayField<ResumeForm> name="languages" newItem={emptyLanguage} addLabel="Add language">
      {(i) => (
        <Grid>
          <TextField<ResumeForm> name={`languages.${i}.language`} label="Language" />
          <TextField<ResumeForm> name={`languages.${i}.fluency`} label="Fluency" />
        </Grid>
      )}
    </ArrayField>
  );
}

export function InterestsSection() {
  return (
    <ArrayField<ResumeForm> name="interests" newItem={emptyInterest} addLabel="Add interest">
      {(i) => (
        <div className="flex flex-col gap-4">
          <TextField<ResumeForm> name={`interests.${i}.name`} label="Interest" />
          <StringList name={`interests.${i}.keywords`} label="Keywords" addLabel="Add keyword" />
        </div>
      )}
    </ArrayField>
  );
}

export function ReferencesSection() {
  return (
    <ArrayField<ResumeForm> name="references" newItem={emptyReference} addLabel="Add reference">
      {(i) => (
        <div className="flex flex-col gap-4">
          <TextField<ResumeForm> name={`references.${i}.name`} label="Name" />
          <TextareaField<ResumeForm> name={`references.${i}.reference`} label="Reference" />
        </div>
      )}
    </ArrayField>
  );
}

export function ProjectsSection() {
  return (
    <ArrayField<ResumeForm> name="projects" newItem={emptyProject} addLabel="Add project">
      {(i) => (
        <div className="flex flex-col gap-4">
          <Grid>
            <TextField<ResumeForm> name={`projects.${i}.name`} label="Name" />
            <TextField<ResumeForm> name={`projects.${i}.entity`} label="Entity" />
            <TextField<ResumeForm> name={`projects.${i}.type`} label="Type" />
            <TextField<ResumeForm> name={`projects.${i}.url`} label="URL" />
            <DateField<ResumeForm> name={`projects.${i}.startDate`} label="Start date" />
            <DateField<ResumeForm> name={`projects.${i}.endDate`} label="End date" />
          </Grid>
          <TextareaField<ResumeForm> name={`projects.${i}.description`} label="Description" />
          <StringList
            name={`projects.${i}.highlights`}
            label="Highlights"
            addLabel="Add highlight"
          />
        </div>
      )}
    </ArrayField>
  );
}

export function MetaSection() {
  return (
    <Grid>
      <TextField<ResumeForm> name="meta.canonical" label="Canonical URL" />
      <TextField<ResumeForm> name="meta.version" label="Version" />
      <TextField<ResumeForm> name="meta.lastModified" label="Last modified" />
    </Grid>
  );
}

export const RESUME_SECTIONS = [
  { id: "basics", label: "Basics", Component: BasicsSection },
  { id: "work", label: "Work", Component: WorkSection },
  { id: "volunteer", label: "Volunteer", Component: VolunteerSection },
  { id: "education", label: "Education", Component: EducationSection },
  { id: "awards", label: "Awards", Component: AwardsSection },
  { id: "certificates", label: "Certificates", Component: CertificatesSection },
  { id: "publications", label: "Publications", Component: PublicationsSection },
  { id: "skills", label: "Skills", Component: SkillsSection },
  { id: "languages", label: "Languages", Component: LanguagesSection },
  { id: "interests", label: "Interests", Component: InterestsSection },
  { id: "references", label: "References", Component: ReferencesSection },
  { id: "projects", label: "Projects", Component: ProjectsSection },
  { id: "meta", label: "Meta", Component: MetaSection },
] as const;
