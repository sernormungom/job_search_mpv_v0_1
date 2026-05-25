| Area                | Current implementation                       | Target platform                                   | Gap                                             |
| ------------------- | -------------------------------------------- | ------------------------------------------------- | ----------------------------------------------- |
| Users               | Mainly individual job seeker                 | Consultants + Talent Advisors                     | Need explicit multi-role model                  |
| Team size           | Single-user local workflow                   | 2–5 consultants                                   | Need consultant identity/profile separation     |
| Opportunity intake  | Manual/configured sources, Verama/Ework      | Job boards, LinkedIn, email, sales leads, portals | Need broader source abstraction                 |
| Standardization     | Python + optional LLM/hybrid                 | AI-assisted robust normalization and translation  | Mostly aligned, needs role/workflow integration |
| Matching            | Batch matching against maintained profile    | Match many opportunities to many consultants      | Need many-to-many matching model                |
| Review              | Dashboard statuses                           | Advisor review + Consultant review                | Need separate approval states                   |
| CV generation       | Selected jobs only                           | Consultant-approved candidate material            | Mostly aligned                                  |
| Tracking            | Persistent CSV tracker                       | Advisor-managed application/submission tracking   | Need multi-consultant tracking and audit model  |
| External publishing | Not implemented; explicit non-goal currently | Future secure customer-facing CV publication      | Major future capability                         |
| Access control      | Local files/session state                    | Role-based access + time-limited external access  | Major future capability                         |
| Integrations        | LLM, Verama/Ework, local files               | OneDrive, LinkedIn, Email, portals, CRM/ATS       | Need integration architecture                   |
| Sensitive data      | Local profile/CV artifacts                   | Multi-user personal + client data                 | Need privacy/security analysis                  |
