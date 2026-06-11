"""PDF resume export (issue #90) via fpdf2.

Pure-Python (no system libraries / headless browser), so it runs identically on
dev (Windows) and in the container. Input is the by-alias json-resume dict.
"""

from __future__ import annotations

from typing import Any

from fpdf import FPDF


def _ascii(value: Any) -> str:
    """fpdf2's core fonts are latin-1; keep text safe by dropping the rest."""
    text = str(value or "")
    return text.encode("latin-1", "replace").decode("latin-1")


def _date_range(item: dict[str, Any]) -> str:
    start = item.get("startDate") or item.get("date") or item.get("releaseDate") or ""
    end = item.get("endDate") or ""
    if start and end:
        return f"{start} - {end}"
    return str(start or end or "")


class _ResumePdf(FPDF):
    def heading(self, text: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.ln(2)
        self.cell(0, 7, _ascii(text), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=10)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", size=10)
        self.multi_cell(0, 5, _ascii(text), new_x="LMARGIN", new_y="NEXT")

    def bold_line(self, text: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(0, 5, _ascii(text), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", size=10)


def render_pdf(name: str, json_resume: dict[str, Any]) -> bytes:
    pdf = _ResumePdf()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    basics = json_resume.get("basics") or {}

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, _ascii(basics.get("name") or name), new_x="LMARGIN", new_y="NEXT")
    if basics.get("label"):
        pdf.set_font("Helvetica", size=11)
        pdf.cell(0, 6, _ascii(basics["label"]), new_x="LMARGIN", new_y="NEXT")

    contact = " | ".join(
        b for b in [basics.get("email"), basics.get("phone"), basics.get("url")] if b
    )
    if contact:
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 6, _ascii(contact), new_x="LMARGIN", new_y="NEXT")

    if basics.get("summary"):
        pdf.heading("Summary")
        pdf.body(basics["summary"])

    def work_block(items: list[dict[str, Any]], heading: str, name_key: str, sub_key: str) -> None:
        if not items:
            return
        pdf.heading(heading)
        for item in items:
            pdf.bold_line(f"{item.get(name_key, '')} {item.get(sub_key, '')}".strip())
            dates = _date_range(item)
            if dates:
                pdf.body(dates)
            if item.get("summary"):
                pdf.body(item["summary"])
            for highlight in item.get("highlights") or []:
                pdf.body(f"- {highlight}")

    work_block(json_resume.get("work") or [], "Experience", "position", "name")
    work_block(json_resume.get("volunteer") or [], "Volunteer", "organization", "position")

    education = json_resume.get("education") or []
    if education:
        pdf.heading("Education")
        for edu in education:
            pdf.bold_line(f"{edu.get('institution', '')} - {edu.get('area', '')}".strip(" -"))
            if edu.get("studyType"):
                pdf.body(edu["studyType"])
            dates = _date_range(edu)
            if dates:
                pdf.body(dates)

    projects = json_resume.get("projects") or []
    if projects:
        pdf.heading("Projects")
        for proj in projects:
            pdf.bold_line(proj.get("name", ""))
            if proj.get("description"):
                pdf.body(proj["description"])
            for highlight in proj.get("highlights") or []:
                pdf.body(f"- {highlight}")

    skills = json_resume.get("skills") or []
    if skills:
        pdf.heading("Skills")
        pdf.body(", ".join(s.get("name", "") for s in skills if s.get("name")))

    return bytes(pdf.output())
