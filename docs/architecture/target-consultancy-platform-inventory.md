# Target Consultancy Platform Inventory

## System name

Consultant Opportunity Matching Platform

## Target architecture type

Small-team consultancy opportunity-matching, review, CV-preparation, and controlled-submission platform.

## Target users

- Consultants
- Talent Advisors

## Future users

- Hiring Managers
- External customer reviewers
- Sales / Account Managers
- Administrators

## Near-term target scope

The system supports a small team of 2–5 consultants. Talent Advisors collect and curate opportunities, the system deduplicates and standardizes them, Talent Advisors approve relevant matches, Consultants review positions in the dashboard, and selected positions move to CV/application material generation.

## Target workflow

Talent Advisor collects opportunities
-> system deduplicates and standardizes
-> system matches against consultant profiles
-> Talent Advisor approves matches
-> Consultant reviews positions
-> Consultant selects positions to apply for
-> system drafts CV/application material
-> Consultant approves generated content
-> Talent Advisor approves final submission
-> future Hiring Manager/customer reviews published candidate material

## Target primary actors

### Consultant

Maintains profile information, approves AI-generated profile/experience/preference data, reviews opportunities, selects positions, and approves generated CV/application material.

### Talent Advisor

Collects opportunities, reviews matches, approves relevant opportunities for consultants, maintains tracking, and approves final CV submission.

### Hiring Manager / Customer Reviewer

Future external or semi-external actor who reviews approved candidate material and decides whether to continue with interview or hiring process.

## Target external sources

- Job boards
- LinkedIn
- Client emails
- Internal sales leads
- OneDrive
- Email
- Client procurement portals
- LLM provider
- Document generation/export service
- Future CRM
- Future ATS

## Target capabilities

- Opportunity intake
- Opportunity deduplication
- Opportunity standardization
- Swedish/English translation
- Consultant profile management
- AI-assisted profile and experience structuring
- Matching and scoring
- Talent Advisor match approval
- Consultant opportunity review
- CV and application package generation
- Consultant approval
- Talent Advisor submission approval
- Secure external publishing
- Time-limited customer access
- Tracking and audit
- Future interview preparation

## Sensitive data areas requiring investigation

- Consultant CVs
- Contact details
- Work history
- Preferences
- Availability
- Client names
- Internal sales leads
- Advisor notes
- Match scores
- Rejection reasons
- AI-generated content
- Published CV links
- Submission history

## Target architectural constraints

- AI assists but does not make final decisions.
- Consultant approves own profile and generated CV material.
- Talent Advisor approves matches and final submission.
- External publishing requires access control and expiry.
- Tracking and auditability are required.
- The system should scale from one consultant to a small team.
- Future integrations should not compromise the local/batch workflow discipline.