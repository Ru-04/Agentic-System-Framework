# WebDesk v0.3.10 — Gate 1 R1/R2 Contract Remediation

**Baseline:** v0.3.9 review candidate. **Status:** review candidate, NOT implementation-approved.

- R1: source-of-truth single-use ceremony Administrator appointment marker; old install approvals cannot re-promote; RoleAssignment carries approval FK, audited consumption, DB trigger; existing active staff may be appointed only by new signed recovery ceremony. Bootstrap role cardinality remains exactly one. Architecture/Governance/Schema and EVAL-F11h aligned.
- R2: corrected reversed EVAL-F11d withdrawal assertion and deterministic HTTP codes; immutable UserWithdrawal added, with pending create approval cancellation in same transaction.
- N1–N4: named withdrawal record, rejection releases target reservation, README version corrected, original v0.3.8 history headings preserved.
- Normative and YAML labels bumped to 0.3.10; all historical changelogs retained.
- **Not ratified:** zero-active-Administrator offline restore/reinstall acceptance, including missed first install activation. No production configuration values fabricated.
