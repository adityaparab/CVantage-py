import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "@/api/analyses";
import { AnalysisResults } from "@/features/analysis/AnalysisResults";

const result: AnalysisResult = {
  overall_score: 82,
  ats_score: 60,
  project_score: 70,
  strong_points: ["Strong Python"],
  weak_points: ["Light on cloud"],
  matching_skills: ["python", "fastapi"],
  skill_gaps: ["kubernetes"],
  suggestions: [
    {
      suggestion_id: "s1",
      group: "wording",
      field_ref: "basics.summary",
      title: "Sharpen the summary",
      description: "Lead with impact.",
      proposed_value: "Senior engineer with 8y…",
      applied: false,
      dismissed: false,
    },
    {
      suggestion_id: "s2",
      group: "wording",
      field_ref: "x",
      title: "Dismissed one",
      description: "…",
      proposed_value: null,
      applied: false,
      dismissed: true,
    },
  ],
  interview_questions: [{ question: "Describe a scaling problem.", suggested_answer: "Sharded." }],
};

describe("AnalysisResults", () => {
  it("renders scores, points, skills, grouped suggestions, and interview Q&A", () => {
    render(<AnalysisResults result={result} />);
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("Strong Python")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("kubernetes")).toBeInTheDocument();
    expect(screen.getByText("Sharpen the summary")).toBeInTheDocument();
    expect(screen.getByText("Senior engineer with 8y…")).toBeInTheDocument();
    // Dismissed suggestions are hidden.
    expect(screen.queryByText("Dismissed one")).not.toBeInTheDocument();
    expect(screen.getByText("Describe a scaling problem.")).toBeInTheDocument();
  });

  it("hides the project gauge when there is no project score", () => {
    render(<AnalysisResults result={{ ...result, project_score: null }} />);
    expect(screen.queryByText("Project score")).not.toBeInTheDocument();
  });
});
