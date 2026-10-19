# v0.3.4 Foundation Final Review Candidate — Change Log

Status: **independent review required; not approved for Claude Code implementation**. No application code changed.

- **R1 / C-5:** Included eligible `pending` Source versions in immutable RunInputSnapshot; parsing is run-stage, not upload-stage; failed source retry gating; extended EVAL-F13.
- **R2 / C-2:** Human self-role and self-membership assignment prohibited by service and database checks; approved audited `system:bootstrap` and `system:project_create` exceptions; added EVAL-F11b.
- **R3 / C-9:** Archive during active run returns 409; archived cancellation permitted if applicable, retries denied; extended EVAL-F09.
- **C-1 residue:** Removed implication parked runs resume before a newer run.
- **Non-blocking:** Quarantined source download denied; EML non-subject/body headers do not form text segments; hash input keys/revision order clarified; version and tracking headers updated.

Original routing/evidence/estimation and release-stage blockers remain deferred.
