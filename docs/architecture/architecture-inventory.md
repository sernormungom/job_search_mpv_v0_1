# Architecture Inventory

## Working title

Consultant Opportunity Matching and CV Preparation Platform

## Current prototype

The current implementation is a local, batch-oriented prototype for job-search automation and CV preparation. It collects job ads, deduplicates them, standardizes and matches them against profile data, creates a dashboard review queue, and generates CV artifacts only for selected jobs.

## Target system vision

The target system supports a consultancy firm in matching consultants to relevant opportunities, preparing tailored candidate material, and coordinating human review and approval before submission.

## Primary actors

### Consultant

A consultant maintains profile information, reviews recommended opportunities, gives approval for CV preparation, and may approve final candidate material before submission.

### Talent Advisor

A talent advisor reviews opportunities, evaluates consultant fit, manages the review queue, prepares or validates CV material, and coordinates with consultants and hiring managers.

### Hiring Manager

A hiring manager reviews consultant suitability for client opportunities, gives feedback, and may approve or reject a proposed submission.

### Sales / Account Manager

A sales or account manager captures client needs, adds opportunities, tracks client relationships, and may submit approved candidate material.

### Administrator

An administrator manages users, permissions, templates, source configuration, and system settings.

## External actors and systems

- Job boards
- Client procurement portals
- Client organizations
- CRM or sales system
- ATS or recruitment system
- Document storage system
- Calendar/email system
- Optional AI/LLM service

## Core business capabilities

- Opportunity intake
- Opportunity normalization
- Consultant profile management
- Matching and ranking
- Human review
- CV and candidate package generation
- Approval workflow
- Submission tracking
- Analytics and reporting
- Template and policy management

## Core domain concepts

- Consultant
- Consultant profile
- Opportunity
- Client
- Match result
- Review decision
- CV artifact
- Candidate package
- Submission
- Template
- Source
- Approval

## Architectural constraints

- Human-in-the-loop by default
- No automatic external submission without approval
- Traceability of decisions and generated artifacts
- Separation between opportunity matching and CV/package generation
- Role-based access for consultants, talent advisors, hiring managers, and administrators
- Clear distinction between maintained source data, generated artifacts, and persistent decision history

## Current implementation mapping

The current local project implements a subset of the target system:

| Current project element | Target architecture concept |
|---|---|
| Job seeker | Consultant |
| Dashboard review queue | Human review workflow |
| Maintained YAML profile data | Consultant profile management |
| Job ads in source folders | Opportunity intake |
| Standardization/matching pipeline | Matching and ranking capability |
| Selected CV pipeline | Candidate package generation |
| Application tracker CSV | Submission/review decision history |
| Local folders | Prototype data stores |

## Open architecture questions

1. Is the primary user the consultant, the talent advisor, or both?
2. Should the target system manage many consultants and many opportunities?
3. Should generated CVs require consultant approval, talent advisor approval, or both?
4. Does the system submit candidate material externally, or only prepare it?
5. Which external systems would matter in a real consultancy: CRM, ATS, document storage, email, calendar, procurement portals?
6. What information is sensitive and requires access control?
7. What should be auditable: match score, CV generation, approval, submission, feedback?