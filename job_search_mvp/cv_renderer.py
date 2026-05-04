#!/usr/bin/env python3
"""Render cv_draft.yaml into local HTML files.

This prototype intentionally renders only from the approved CV draft object.
It does not rewrite content, invent content, or call an LLM.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .paths import resolve_data_dir

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def load_yaml(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        return data or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Could not parse {path}. Install PyYAML with: python -m pip install pyyaml"
        ) from exc


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "cv"


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def list_items(items: List[str]) -> str:
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def inline_items(items: List[str]) -> str:
    return " · ".join(esc(item) for item in items)


def get_employee_name(employee_profile: Dict[str, Any], fallback: str) -> str:
    employee = employee_profile.get("employee", {}) if isinstance(employee_profile, dict) else {}
    return employee.get("display_name") or fallback


def render_html(
    cv_draft: Dict[str, Any],
    employee_profile: Dict[str, Any],
    job_standardized: Optional[Dict[str, Any]] = None,
    include_evidence: bool = False,
) -> str:
    draft = cv_draft.get("cv_draft", cv_draft)
    sections = draft.get("sections", {})
    employee_name = get_employee_name(employee_profile, draft.get("employee_id", "Candidate"))
    job = (job_standardized or {}).get("job_standardized", job_standardized or {})
    job_identity = job.get("identity", {}) if isinstance(job, dict) else {}
    target_title = job_identity.get("normalized_title") or job_identity.get("original_title") or "Target role"
    company = job_identity.get("company") or "Target company"

    summary = sections.get("professional_summary", {})
    summary_text = summary.get("text", "")
    tech = sections.get("tech_competence", {})
    experience = sections.get("experience", [])
    validation = draft.get("validation", {})
    reviewer_notes = draft.get("notes_for_reviewer", [])

    evidence_sections = ""
    if include_evidence:
        summary_evidence = summary.get("evidence_links", [])
        exp_evidence_rows: List[str] = []
        for role in experience:
            for bullet in role.get("bullets", []):
                exp_evidence_rows.append(
                    "<tr>"
                    f"<td>{esc(role.get('role_group_id'))}</td>"
                    f"<td>{esc(bullet.get('text'))}</td>"
                    f"<td>{esc(', '.join(bullet.get('evidence_links', [])))}</td>"
                    "</tr>"
                )
        evidence_sections = f"""
        <section class="debug evidence-debug">
          <h2>Evidence trace</h2>
          <p><strong>Summary evidence:</strong> {esc(', '.join(summary_evidence))}</p>
          <table>
            <thead><tr><th>Role group</th><th>Rendered bullet</th><th>Evidence IDs</th></tr></thead>
            <tbody>{''.join(exp_evidence_rows)}</tbody>
          </table>
        </section>
        """

    tech_columns = []
    for title in ["Programming", "Knowledge", "Soft Skills"]:
        tech_columns.append(
            f"""
            <div class="tech-column">
              <h3>{esc(title)}</h3>
              <p>{inline_items(tech.get(title, []))}</p>
            </div>
            """
        )

    exp_html = []
    for role in experience:
        bullets = role.get("bullets", [])
        exp_html.append(
            f"""
            <article class="role">
              <h3>{esc(role.get('role_header'))}</h3>
              <ul>{''.join(f'<li>{esc(b.get("text"))}</li>' for b in bullets)}</ul>
            </article>
            """
        )

    validation_badges = []
    one_page = validation.get("one_page_estimate")
    if one_page:
        validation_badges.append(f"<span class=\"badge\">One-page estimate: {esc(one_page)}</span>")
    unsupported = validation.get("unsupported_claims", [])
    validation_badges.append(f"<span class=\"badge\">Unsupported claims: {len(unsupported)}</span>")
    missing_terms = validation.get("mandatory_terms_not_surfaced", [])
    if missing_terms:
        validation_badges.append(f"<span class=\"badge warning\">Missing terms: {esc(', '.join(missing_terms))}</span>")

    notes_html = ""
    if reviewer_notes:
        notes_html = f"""
        <section class="reviewer-notes no-print">
          <h2>Reviewer notes</h2>
          <ul>{list_items(reviewer_notes)}</ul>
        </section>
        """

    rendered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(employee_name)} - CV for {esc(target_title)}</title>
  <style>
    :root {{
      --text: #1f2933;
      --muted: #53606d;
      --line: #d8dee6;
      --soft: #f5f7fa;
      --accent: #111827;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      background: #eef1f5;
      line-height: 1.35;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      margin: 16px auto;
      padding: 16mm 15mm;
      background: white;
      box-shadow: 0 8px 30px rgba(0,0,0,0.10);
    }}
    header {{ border-bottom: 2px solid var(--accent); padding-bottom: 8px; margin-bottom: 12px; }}
    h1 {{ margin: 0; font-size: 24px; letter-spacing: 0.2px; }}
    .subtitle {{ margin-top: 3px; color: var(--muted); font-size: 12px; }}
    h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; margin: 14px 0 6px; color: var(--accent); }}
    h3 {{ font-size: 11.5px; margin: 8px 0 4px; }}
    p {{ margin: 0 0 6px; font-size: 10.5px; }}
    ul {{ margin: 4px 0 0 17px; padding: 0; }}
    li {{ margin: 0 0 3px; font-size: 10.2px; }}
    .tech-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
    .tech-column {{ border: 1px solid var(--line); padding: 6px; background: var(--soft); }}
    .tech-column h3 {{ margin-top: 0; }}
    .tech-column p {{ font-size: 9.8px; }}
    .role {{ break-inside: avoid; page-break-inside: avoid; }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }}
    .badge {{ display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 2px 7px; font-size: 9px; color: var(--muted); }}
    .badge.warning {{ color: #7a4b00; border-color: #d6a84f; }}
    .reviewer-notes {{ margin-top: 18px; padding: 10px; background: #fff9e8; border: 1px solid #eed17d; }}
    .debug {{ margin-top: 18px; padding: 10px; border: 1px dashed var(--line); }}
    table {{ border-collapse: collapse; width: 100%; font-size: 9px; }}
    th, td {{ border: 1px solid var(--line); padding: 4px; text-align: left; vertical-align: top; }}
    footer {{ margin-top: 10px; color: var(--muted); font-size: 8.5px; }}
    @page {{ size: A4; margin: 10mm; }}
    @media print {{
      body {{ background: white; }}
      .page {{ box-shadow: none; margin: 0; width: auto; min-height: auto; padding: 0; }}
      .no-print {{ display: none !important; }}
      h2 {{ margin-top: 10px; }}
      li {{ margin-bottom: 2px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <h1>{esc(employee_name)}</h1>
      <div class="subtitle">Tailored CV draft for {esc(target_title)} · {esc(company)}</div>
    </header>

    <section>
      <h2>Professional Summary</h2>
      <p>{esc(summary_text)}</p>
    </section>

    <section>
      <h2>Tech Competence</h2>
      <div class="tech-grid">{''.join(tech_columns)}</div>
    </section>

    <section>
      <h2>Experience</h2>
      {''.join(exp_html)}
    </section>

    <section class="no-print">
      <h2>Validation</h2>
      <div class="badges">{''.join(validation_badges)}</div>
    </section>

    {notes_html}
    {evidence_sections}

    <footer class="no-print">Generated locally from cv_draft.yaml at {esc(rendered_at)}. Review before sending or publishing.</footer>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a CV draft into local HTML.")
    parser.add_argument("--cv-draft", required=True, help="Path to cv_draft.yaml")
    parser.add_argument("--job-standardized", required=False, help="Optional path to job_standardized.yaml")
    parser.add_argument("--data-dir", default="data", help="Folder containing employee_profile.yaml")
    parser.add_argument("--out-dir", default="outputs/single", help="Output folder")
    parser.add_argument("--include-evidence", action="store_true", help="Also create a debug HTML with evidence trace")
    args = parser.parse_args()

    cv_draft_path = Path(args.cv_draft)
    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cv_draft = load_yaml(cv_draft_path)
    employee_profile = load_yaml(data_dir / "employee_profile.yaml")
    job_standardized = load_yaml(Path(args.job_standardized)) if args.job_standardized else None

    draft = cv_draft.get("cv_draft", cv_draft)
    job_id = draft.get("job_id") or slugify(cv_draft_path.stem)

    html_doc = render_html(cv_draft, employee_profile, job_standardized, include_evidence=False)
    out_html = out_dir / f"{job_id}.cv.html"
    out_html.write_text(html_doc, encoding="utf-8")

    print(f"Wrote {out_html}")

    if args.include_evidence:
        debug_doc = render_html(cv_draft, employee_profile, job_standardized, include_evidence=True)
        debug_html = out_dir / f"{job_id}.cv.debug.html"
        debug_html.write_text(debug_doc, encoding="utf-8")
        print(f"Wrote {debug_html}")


if __name__ == "__main__":
    main()
