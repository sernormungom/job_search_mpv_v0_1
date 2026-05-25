workspace "Consultant Opportunity Matching Platform" "C4 architecture model for a consultancy opportunity matching and CV preparation platform." {

    !identifiers hierarchical

    model {
        consultant = person "Consultant" "Maintains profile and experience information, reviews opportunities, selects positions to apply for, and approves generated CV/application material."

        talentAdvisor = person "Talent Advisor" "Collects and curates opportunities, approves relevant matches, tracks applications, and approves final CV submission."

        hiringManager = person "Hiring Manager / Customer Reviewer" "Reviews approved candidate material and decides whether to proceed with interview or hiring process."

        salesAccountManager = person "Sales / Account Manager" "Provides internal sales leads and client opportunity information." {
            tags "Future"
        }

        system = softwareSystem "Consultant Opportunity Matching Platform" "Collects, deduplicates, standardizes, translates, and matches opportunities against consultant profiles, then supports review, CV preparation, approval, tracking, and future controlled publication."

        jobBoards = softwareSystem "Job Boards" "Public sources of job ads and consultancy assignment opportunities." {
            tags "External System"
        }

        linkedIn = softwareSystem "LinkedIn" "Source of job posts, recruiter messages, and professional opportunity signals." {
            tags "External System"
        }

        emailSystem = softwareSystem "Email System" "Source of client emails, recruiter messages, and opportunity-related communication." {
            tags "External System"
        }

        oneDrive = softwareSystem "OneDrive" "Shared storage location used to copy or transfer opportunity descriptions into the intake workflow." {
            tags "External System"
        }

        procurementPortals = softwareSystem "Client Procurement Portals" "External customer portals containing assignment requests and future submission destinations." {
            tags "External System", "Future"
        }

        llmProvider = softwareSystem "LLM Provider" "Provides AI assistance for standardization, Swedish/English translation, tag refinement, matching support, and CV/application draft generation." {
            tags "External System"
        }

        documentExport = softwareSystem "Document Generation / Export" "Generates or exports CVs, cover letters, candidate summaries, and application packages." {
            tags "External System"
        }

        secureCandidateSite = softwareSystem "Secure Candidate Publication Site" "Future customer-facing site for time-limited, access-controlled review of approved candidate material." {
            tags "External System", "Future"
        }

        crm = softwareSystem "CRM System" "Future system of record for clients, customer contacts, sales leads, and account activity." {
            tags "External System", "Future"
        }

        ats = softwareSystem "ATS / Recruitment System" "Future system for tracking candidate submissions, recruitment stages, interviews, and hiring decisions." {
            tags "External System", "Future"
        }

        consultant -> system "Maintains profile, reviews opportunities, selects positions, and approves generated material"
        talentAdvisor -> system "Collects opportunities, reviews matches, tracks applications, and approves submissions"
        hiringManager -> system "Reviews approved candidate material and provides feedback"
        salesAccountManager -> system "Provides internal leads and client opportunity information"

        system -> jobBoards "Imports or receives job ads and assignment opportunities from"
        system -> linkedIn "Uses job posts and recruiter/opportunity information from"
        system -> emailSystem "Receives or processes opportunity information from"
        system -> oneDrive "Reads copied opportunity descriptions from"
        system -> procurementPortals "May import assignment requests from and later publish/submit approved material to"
        system -> llmProvider "Uses AI assistance for standardization, translation, tag refinement, matching support, and draft generation"
        system -> documentExport "Generates and exports CV/application artifacts using"
        system -> secureCandidateSite "Publishes approved candidate material to, with access control and expiry"
        system -> crm "May synchronize client, lead, and opportunity information with"
        system -> ats "May synchronize candidate submission and hiring-process status with"
    }

    views {
        systemContext system "SystemContext" "System Context diagram for the Consultant Opportunity Matching Platform." {
            include *
            autolayout lr
        }

        styles {
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }

            element "Software System" {
                background #1168bd
                color #ffffff
            }

            element "External System" {
                background #999999
                color #ffffff
            }

            element "Future" {
                border dashed
                opacity 60
            }
        }

        theme default
    }
}