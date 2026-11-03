# Credential exposure record (sanitized), 3 November 2026

**Status: CLOSED BY WDS MANAGEMENT ATTESTATION — INDEPENDENT TECHNICAL EVIDENCE NOT AVAILABLE IN REPOSITORY.**
(Recorded 3 November 2026. WDS Authorized Approver disposition.)

Neither the original nor the replacement password is recorded here, in the repository, or in any commit.

## What happened
- During Sprint 8 engineering, a PostgreSQL connection-string error echoed a connection string that
  contained a password. The password came from the main checkout's git-ignored file
  `.env.integration.local`, for role `webdesk_integration_owner`. The value appeared in two tool
  outputs in the engineering session. It was not written to any repository file or commit.
- The value is identified by a SHA-256 prefix only: `c6834f84593a`.

## Identification (done before closure)
- Role: `webdesk_integration_owner`. Configured target in the file: `localhost:5433`, database `webdesk_integration`.
- Local copies: a fingerprint check of the `.env*` files in the main checkout and in every worktree found the value in
  `.env.integration.local` only.
- Tracking: `.env.integration.local` is git-ignored (`.gitignore`). It is not tracked by git.
- Validity: at identification time nothing listened on `localhost:5433`. One login attempt on `127.0.0.1:56544`
  failed authentication. Reuse on any other shared cluster was not tested by the engineering session.

## Rotation and verification (owner confirmation)
- The authorized infrastructure owner confirmed on 3 November 2026 that the `webdesk_integration_owner` password
  was rotated and that the rotation passed the owner's verification.
- WDS authorized closure of T-31 on that confirmation, provided this record captures the owner's confirmation and
  the available supporting evidence.
- Basis of closure, stated precisely: the confirmation was relayed to the engineering session in a WDS directive.
  The directive is not in this repository. The owner's own written confirmation artifact, if one exists, is held
  by the owner. This record does not show that a written confirmation was received, and it does not claim one.

## Disposition and the distinctions it preserves
- The infrastructure owner confirmed rotation to WDS, and WDS accepted that confirmation as a management disposition.
  A separate written owner confirmation is not mandatory for this disposition.
- No written owner confirmation is present in this repository.
- Independent QA did not itself verify the secret rotation. No independent technical check of the rotation exists here.
- No authentication-log review has been completed or is evidenced.
- This disposition closes the management evidence question. It does not override any mandatory independent technical
  security control.

## What this record does NOT claim
- It does not record the owner's verification steps in detail. The engineering session did not perform or observe them.
- It does not claim that a login-log review for the exposure window was performed. No such review is evidenced here.
  If one is required, the infrastructure owner must supply it.
- The owner-confirmed date is the date of confirmation as recorded above. The owner did not supply a separate
  rotation timestamp.

## Not reused
- The Sprint 8 verification did not use this value. It used dedicated clusters with generated credentials held
  in scratch files outside the repository.

## Residual conditions for the record
1. The infrastructure owner's rotation evidence, if one is needed for audit, is held by that owner and not in this repository.
2. Any login-log review for 3 November 2026 onward remains the owner's to supply, if WDS requires it.
3. The owner's written confirmation, if WDS requires a written record, is to be filed by WDS or the owner. It is not in this repository.
