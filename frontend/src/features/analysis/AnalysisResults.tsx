import type { AnalysisResult } from "@/api/analyses";
import { Badge } from "@/components/ui";

const GROUP_LABELS: Record<string, string> = {
  ats_improvement: "ATS improvements",
  skill_emphasis: "Skill emphasis",
  wording: "Wording",
  skill_addition: "Skill additions",
  project: "Projects",
};

function scoreTone(score: number): "success" | "warn" | "danger" {
  if (score >= 75) return "success";
  if (score >= 50) return "warn";
  return "danger";
}

function ScoreGauge({ label, score }: { label: string; score: number }) {
  const tone = scoreTone(score);
  const color = tone === "success" ? "text-success" : tone === "warn" ? "text-warn" : "text-danger";
  const bar = tone === "success" ? "bg-success" : tone === "warn" ? "bg-warn" : "bg-danger";
  return (
    <div className="rounded-card border border-border bg-card p-5 text-center">
      <p className="text-sm text-muted">{label}</p>
      <p className={`mt-1 text-4xl font-bold ${color}`}>{score}</p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div className={`h-full ${bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function PointList({ title, points, tone }: { title: string; points: string[]; tone: string }) {
  if (points.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-text">{title}</h3>
      <ul className="flex flex-col gap-1.5">
        {points.map((p, i) => (
          <li key={i} className="flex gap-2 text-sm text-text">
            <span className={tone} aria-hidden="true">
              •
            </span>
            {p}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AnalysisResults({
  result,
  actions,
}: {
  result: AnalysisResult;
  actions?: React.ReactNode;
}) {
  const activeSuggestions = (result.suggestions ?? []).filter((s) => !s.dismissed);
  const groups = [...new Set(activeSuggestions.map((s) => s.group))];
  const matchingSkills = result.matching_skills ?? [];
  const skillGaps = result.skill_gaps ?? [];
  const interviewQuestions = result.interview_questions ?? [];

  return (
    <div className="flex flex-col gap-8">
      <section className="grid gap-4 sm:grid-cols-3" aria-label="Scores">
        <ScoreGauge label="Overall match" score={result.overall_score} />
        <ScoreGauge label="ATS score" score={result.ats_score} />
        {result.project_score !== null && (
          <ScoreGauge label="Project score" score={result.project_score} />
        )}
      </section>

      <section className="grid gap-6 sm:grid-cols-2">
        <PointList title="Strengths" points={result.strong_points ?? []} tone="text-success" />
        <PointList title="Weaknesses" points={result.weak_points ?? []} tone="text-danger" />
      </section>

      <section className="grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Matching skills</h3>
          <div className="flex flex-wrap gap-2">
            {matchingSkills.length === 0 ? (
              <p className="text-sm text-muted">None detected.</p>
            ) : (
              matchingSkills.map((s) => (
                <Badge key={s} tone="success">
                  {s}
                </Badge>
              ))
            )}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Skill gaps</h3>
          <div className="flex flex-wrap gap-2">
            {skillGaps.length === 0 ? (
              <p className="text-sm text-muted">None detected.</p>
            ) : (
              skillGaps.map((s) => (
                <Badge key={s} tone="warn">
                  {s}
                </Badge>
              ))
            )}
          </div>
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text">Suggestions</h2>
          {actions}
        </div>
        {activeSuggestions.length === 0 ? (
          <p className="text-sm text-muted">No suggestions.</p>
        ) : (
          <div className="flex flex-col gap-5">
            {groups.map((group) => (
              <div key={group}>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  {GROUP_LABELS[group] ?? group}
                </h3>
                <ul className="flex flex-col gap-2">
                  {activeSuggestions
                    .filter((s) => s.group === group)
                    .map((s) => (
                      <li key={s.suggestion_id} className="rounded-card border border-border p-4">
                        <p className="font-medium text-text">{s.title}</p>
                        <p className="mt-1 text-sm text-muted">{s.description}</p>
                        {s.proposed_value && (
                          <p className="mt-2 rounded-md bg-accent-soft px-3 py-2 text-sm text-accent-text">
                            {s.proposed_value}
                          </p>
                        )}
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      {interviewQuestions.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-text">Interview questions</h2>
          <div className="flex flex-col gap-2">
            {interviewQuestions.map((q, i) => (
              <details key={i} className="rounded-card border border-border p-4">
                <summary className="cursor-pointer text-sm font-medium text-text">
                  {q.question}
                </summary>
                <p className="mt-2 text-sm text-muted">{q.suggested_answer}</p>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
