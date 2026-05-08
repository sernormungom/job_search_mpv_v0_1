#!/usr/bin/env python3
"""Render a CV draft into an MPYA Sci & Tech inspired HTML CV.

This renderer is intentionally template-based. It does not rewrite CV content;
it only formats an approved cv_draft.yaml into a consultancy-style layout.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .paths import default_assets_dir, resolve_data_dir

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required for this renderer. Install with: python -m pip install pyyaml") from exc


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def split_role_header(role_header: str) -> Tuple[str, str, str]:
    """Return (title, company, dates) from common role_header formats."""
    # Generated pattern: Title, Company, dates
    parts = [p.strip() for p in role_header.split(",")]
    if len(parts) >= 3:
        title = parts[0]
        # Company may itself contain slash, but dates usually in last part(s)
        dates = parts[-1]
        company = ", ".join(parts[1:-1])
        return title, company, dates
    return role_header, "", ""


def collect_role_group_tools(exp_db: Dict[str, Any], role_group_id: str) -> List[str]:
    out: List[str] = []
    for rg in exp_db.get("experience_role_groups", []):
        if rg.get("role_group_id") != role_group_id:
            continue
        for block in rg.get("blocks", []) or []:
            for key in ["languages", "tools", "standards_processes", "verification_validation"]:
                for item in block.get(key, []) or []:
                    if item and item not in out:
                        out.append(str(item))
    # Keep the line useful and not too long
    return out[:18]


def get_static(static_data: Dict[str, Any]) -> Dict[str, Any]:
    return static_data.get("consultancy_profile", static_data)


def merge_profile(static_profile: Dict[str, Any], employee_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer employee-owned CV profile fields, keep legacy fallback."""
    merged = dict(static_profile or {})
    cv_static = employee_profile.get("cv_static_profile", {}) if isinstance(employee_profile, dict) else {}
    if not isinstance(cv_static, dict):
        cv_static = {}

    for key in ["language_skills", "education", "additional_courses_trainings_workshops"]:
        value = cv_static.get(key)
        if value:
            merged[key] = value
    return merged


def ul(items: List[str], klass: str = "") -> str:
    if not items:
        return ""
    return f'<ul class="{klass}">' + "".join(f"<li>{e(x)}</li>" for x in items if x) + "</ul>"


def asset_uri(path: Path) -> str:
    return path.resolve().as_uri()


def paragraph(text: str) -> str:
    return f"<p>{e(text)}</p>" if text else ""


def css() -> str:
    return r"""
:root {
  --mpya-purple: #a3258e;
  --mpya-purple-dark: #8e1f7f;
  --side-bg: #dfe3da;
  --text: #111111;
  --muted: #555555;
  --line: #b02694;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #eeeeee; color: var(--text); font-family: Arial, Helvetica, sans-serif; }
.cv-page { width: 210mm; height: 297mm; min-height: 297mm; margin: 0 auto 12mm auto; background: white; position: relative; overflow: hidden; page-break-after: always; }
.cv-page:last-child { page-break-after: auto; }
.header { height: 38mm; background: var(--mpya-purple); color: white; display: grid; grid-template-columns: 1fr 40mm; align-items: center; padding: 8mm 8mm; }
.header .headline { font-size: 13.5pt; margin-bottom: 5mm; font-weight: 400; letter-spacing: -0.2px; }
.header .name { font-size: 24pt; font-weight: 700; line-height: 1; }
.logo { text-align: right; font-size: 25pt; letter-spacing: 1px; line-height: .9; font-weight: 300; }
.logo small { display: block; font-size: 6.5pt; letter-spacing: 4px; font-weight: 700; margin-top: 2mm; }
.logo img { max-width: 38mm; max-height: 23mm; object-fit: contain; }
.page-grid { display: grid; grid-template-columns: 57mm 1fr; min-height: calc(297mm - 38mm); }
.side { background: var(--side-bg); padding: 0; position: relative; }
.main { padding: 10mm 7mm 12mm 9mm; font-size: 8.7pt; line-height: 1.32; }
.photo { width: 57mm; height: 56mm; object-fit: cover; display: block; filter: grayscale(100%); }
.side-label { color: var(--mpya-purple); font-size: 17pt; font-weight: 400; padding: 14mm 6mm 0 8mm; }
.side-label.comp { padding-top: 22mm; }
.side-label.experience { position: absolute; top: 167mm; left: 0; right: 0; }
.side-label.education { padding-top: 40mm; }
.rule { height: 1px; background: var(--line); margin: 0 0 6mm 0; }
.summary { max-width: 126mm; font-size: 9.5pt; line-height: 1.28; margin: 0 0 9mm 0; }
.availability { font-size: 9.5pt; margin: 0 0 10mm 0; }
.availability strong { font-weight: 800; }
.tech-grid { display: grid; grid-template-columns: 1fr 1.1fr .9fr; gap: 9mm; color: var(--mpya-purple-dark); }
.tech-grid h3 { margin: 0 0 4mm 0; font-size: 8.8pt; color: var(--mpya-purple-dark); }
ul { margin: 0; padding-left: 4mm; }
li { margin: 0 0 1.5mm 0; }
.tech-grid li { margin-bottom: 1.35mm; }
.section-title { color: var(--mpya-purple); font-size: 17pt; font-weight: 400; margin: 0; }
.experience-start { margin-top: 17mm; }
.experience-rule { margin-top: 2mm; }
.role-row { display: grid; grid-template-columns: 57mm 1fr; page-break-inside: avoid; }
.role-side { background: var(--side-bg); padding: 6mm 5mm 3mm 8mm; font-size: 8.2pt; line-height: 1.28; }
.role-side .company { font-weight: 700; }
.role-side .date { margin-top: 2mm; color: #222; }
.role-main { padding: 6mm 7mm 2mm 9mm; font-size: 8.2pt; line-height: 1.34; }
.role-title { font-size: 10pt; font-weight: 800; margin-bottom: 2mm; }
.role-date { margin-bottom: 2mm; }
.role-main ul { padding-left: 4mm; }
.role-main li { margin-bottom: 1.8mm; }
.tools { margin: 2.5mm 0 2mm 0; font-size: 8pt; }
.tools strong { font-weight: 800; }
.footer { position: absolute; left: 66mm; right: 8mm; bottom: 7mm; font-size: 7.6pt; display: flex; justify-content: space-between; align-items: flex-end; }
.footer-logo { color: var(--mpya-purple); text-align: right; font-size: 25pt; letter-spacing: 1px; line-height: .9; }
.footer-logo small { display: block; font-size: 6.3pt; letter-spacing: 4px; font-weight: 700; }
.edu-main { padding-top: 40mm; }
.edu-grid { display: grid; grid-template-columns: 40mm 1.05fr 1.2fr; gap: 8mm; font-size: 8pt; line-height: 1.3; }
.edu-grid h3 { font-size: 9.5pt; margin: 0 0 2mm 0; }
.edu-item { margin-bottom: 4mm; }
.edu-item .degree { font-weight: 800; font-size: 10pt; }
.edu-item .institution { margin-top: 1mm; }
.edu-item .period { margin-top: 1mm; }
.compact-list li { margin-bottom: 2mm; }
@media print {
  html, body { background: white; }
  .cv-page { margin: 0; width: 210mm; min-height: 297mm; box-shadow: none; }
}
@page { size: A4; margin: 0; }
"""


def render_header(profile: Dict[str, Any], assets_dir: Path) -> str:
    logo_path = assets_dir / "mpya_logo_on_purple.png"
    if logo_path.exists():
        logo = f'<img src="{e(asset_uri(logo_path))}" alt="MPYA Sci & Tech logo" />'
    else:
        logo = 'MPYA.<small>SCI &amp; TECH</small>'
    return f"""
    <div class="header">
      <div>
        <div class="headline">{e(profile.get('headline', 'Software Engineer'))}</div>
        <div class="name">{e(profile.get('name', ''))}</div>
      </div>
      <div class="logo">{logo}</div>
    </div>
    """


def render_page1(draft: Dict[str, Any], profile: Dict[str, Any], assets_dir: Path) -> str:
    sections = draft.get("sections", {})
    summary = sections.get("professional_summary", {}).get("text", "")
    tech = sections.get("tech_competence", {})
    photo_path = assets_dir / "mpya_profile_photo.png"
    photo = f'<img class="photo" src="{e(asset_uri(photo_path))}" alt="Profile photo" />' if photo_path.exists() else '<div class="photo"></div>'
    return f"""
<section class="cv-page">
  {render_header(profile, assets_dir)}
  <div class="page-grid">
    <aside class="side">
      {photo}
      <div class="side-label comp">Tech competence</div>
      <div class="side-label experience">Experience</div>
    </aside>
    <main class="main">
      <div class="summary">{paragraph(summary)}</div>
      <div class="availability"><strong>AVAILABILITY</strong> {e(profile.get('availability', 'According to agreement'))}</div>
      <div class="tech-grid">
        <div><h3>Programming</h3>{ul(tech.get('Programming', []))}</div>
        <div><h3>Experience/Certifications</h3>{ul(tech.get('Knowledge', []))}</div>
        <div><h3>Leadership</h3>{ul(tech.get('Soft Skills', []))}</div>
      </div>
      <div class="experience-start"><div class="rule experience-rule"></div></div>
    </main>
  </div>
</section>
"""


def render_experience_pages(draft: Dict[str, Any], exp_db: Dict[str, Any], profile: Dict[str, Any]) -> str:
    sections = draft.get("sections", {})
    roles = sections.get("experience", []) or []
    rows = []
    for role in roles:
        role_header = role.get("role_header", "")
        title, company, dates = split_role_header(role_header)
        # Special case generated GE title is very long; allow line wrapping.
        tools = collect_role_group_tools(exp_db, role.get("role_group_id", ""))
        bullets = [b.get("text", "") for b in role.get("bullets", []) or []]
        rows.append(f"""
<div class="role-row">
  <aside class="role-side">
    <div class="company">{e(company)}</div>
    <div class="date">{e(dates)}</div>
  </aside>
  <main class="role-main">
    <div class="role-title">{e(title)}</div>
    <div class="role-date">{e(dates)}</div>
    {ul(bullets)}
    {f'<div class="tools"><strong>Tools &amp; Skills:</strong> {e(", ".join(tools))}</div>' if tools else ''}
  </main>
</div>
""")
    footer = render_footer(profile, include_logo=True)
    return f"""
<section class="cv-page">
  {''.join(rows)}
  {footer}
</section>
"""


def render_footer(profile: Dict[str, Any], include_logo: bool = False) -> str:
    ta = profile.get("talent_advisor", {}) or {}
    contact = f"For more information, contact: Talent Advisor {e(ta.get('name', ''))}<br>E: {e(ta.get('email', ''))} M: {e(ta.get('mobile', ''))}"
    logo = '<div class="footer-logo">MPYA.<small>SCI &amp; TECH</small></div>' if include_logo else '<div></div>'
    return f'<div class="footer"><div>{contact}</div>{logo}</div>'


def render_education_page(profile: Dict[str, Any]) -> str:
    langs = profile.get("language_skills", []) or []
    edu_items = []
    for ed in profile.get("education", []) or []:
        details = ed.get("details", []) or []
        edu_items.append(f"""
<div class="edu-item">
  <div class="degree">{e(ed.get('degree'))}</div>
  <div class="institution">{e(ed.get('institution'))}</div>
  <div class="period">{e(ed.get('period'))}</div>
  {ul(details)}
</div>
""")
    courses = profile.get("additional_courses_trainings_workshops", []) or []
    return f"""
<section class="cv-page">
  <div class="page-grid">
    <aside class="side"><div class="side-label education">Education</div></aside>
    <main class="main edu-main">
      <div class="rule"></div>
      <div class="edu-grid">
        <div><h3>Language skills</h3>{ul(langs, 'compact-list')}</div>
        <div>{''.join(edu_items)}</div>
        <div><h3>Additional courses/trainings/workshops</h3>{ul(courses, 'compact-list')}</div>
      </div>
    </main>
  </div>
  {render_footer(profile, include_logo=True)}
</section>
"""


def render_html(
    draft: Dict[str, Any],
    exp_db: Dict[str, Any],
    static_data: Dict[str, Any],
    employee_profile: Dict[str, Any],
    assets_dir: Path,
) -> str:
    profile = merge_profile(get_static(static_data), employee_profile)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{e(profile.get('name'))} - Consultancy CV</title>
<style>{css()}</style>
</head>
<body>
{render_page1(draft, profile, assets_dir)}
{render_experience_pages(draft, exp_db, profile)}
{render_education_page(profile)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an MPYA-style consultancy HTML CV from cv_draft.yaml")
    parser.add_argument("--cv-draft", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--static-profile", type=Path, default=None)
    parser.add_argument("--assets-dir", type=Path, default=None)
    args = parser.parse_args()

    draft_yaml = load_yaml(args.cv_draft)
    draft = draft_yaml.get("cv_draft", draft_yaml)
    data_dir = resolve_data_dir(args.data_dir)
    exp_db = load_yaml(data_dir / "experience_database.yaml")
    employee_profile = load_yaml(data_dir / "employee_profile.yaml")
    static_path = args.static_profile or (data_dir / "consultancy_static_profile.yaml")
    static_data = load_yaml(static_path) if static_path.exists() else {}
    assets_dir = args.assets_dir or default_assets_dir()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    job_id = draft.get("job_id") or args.cv_draft.stem.replace(".cv_draft", "")
    out = args.out_dir / f"{job_id}.mpya_cv.html"
    out.write_text(render_html(draft, exp_db, static_data, employee_profile, assets_dir), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
