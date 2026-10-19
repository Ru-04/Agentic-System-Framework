# v0.3.3 Foundation Approval Candidate — Change Log

This package patches the v0.3.2 specifications only. No application code.

| Correction | Changed contract |
|---|---|
| C-1 / R-01–02 | Analyst-only `run.start`, including after parked runs; Admin cancel/retry/resume; parked cannot resume |
| C-2 / R-03 | Database and service prohibition on self-grants; 403 and audit |
| C-3 / R-04 | Assigned/Granted/class-authorized/content-grant mapped to records |
| C-4 / R-05 | All mutations, denials and client-byte reads audited; sensitive-personal-data redaction restored |
| C-5 / R-06 | Immutable RunInputSnapshot, source-version filters and in-flight stale handling |
| C-6 / R-07 | Persistent reusable segment IDs with composite uniqueness |
| C-7 / R-08 | Quarantine without bypass; restricted unscanned blocked |
| C-8 / R-09 | Explicit tuple ordering and two config inputs for SHA-256 over RFC 8785 JSON |
| C-9 / R-10 | Archived project is read-only, no unarchive in Gate 1 |

Non-blocking repairs: normative version headers, D-05 register status, EML subject/body handling, attachment metadata, corrupt-file 422, expanded EVAL-F01–F10 and EVAL-F11–F13, corrected legacy reference report. The later-phase routing issue remains explicitly outstanding.
