# Credential exposure record (sanitized), 3 November 2026

**Status: OPEN. Rotation has NOT been performed and is NOT verified.**

## What happened
- During Sprint 8 engineering, a PostgreSQL connection-string error echoed a connection string that
  contained a password. The password came from the main checkout's git-ignored file
  `.env.integration.local`, for role `webdesk_integration_owner`. The value appeared in two tool
  outputs in the engineering session. It was not written to any repository file or commit.
- The value is identified by a SHA-256 prefix only: `c6834f84593a`.

## Identification (done)
- Role: `webdesk_integration_owner`. Configured target in the file: `localhost:5433`, database `webdesk_integration`.
- Local copies: a fingerprint check of the `.env*` files in the main checkout and in every worktree found the value in
  `.env.integration.local` only. The copy in `foundation-phase-3` has a different value.
- Tracking: `.env.integration.local` is git-ignored (`.gitignore`). It is not tracked by git.
- Validity: at verification time nothing listened on `localhost:5433`. One login attempt on `127.0.0.1:56544`
  (scratch cluster for G0) failed authentication. Whether the value is valid elsewhere has NOT been tested.
  Testing it against other shared clusters would have been an unapproved probe, so it was not done.

## Reuse (partly checked)
- No other local env file contains the value.
- Reuse on any shared cluster or CI system is UNKNOWN. An inventory by the credential owner is required.

## Actions not performed (and why)
| Action | Status | Reason |
|---|---|---|
| Notify the credential owner through the established secure process | NOT DONE | The engineering session has no approved notification channel. The WDS owner or the infrastructure owner must be informed. |
| Rotate the password for `webdesk_integration_owner` on each cluster where it is valid | NOT DONE | The cluster and role are owned by another environment. Rotation there is outside this engineering session. |
| Verify the old password no longer works | NOT POSSIBLE here | Depends on rotation. |
| Update authorized secret configuration | NOT DONE | Depends on rotation. The owner updates the local file. |

## Not reused
- The Sprint 8 verification did not use this value. It used a dedicated cluster (`127.0.0.1:55808`) with a
  password generated for that cluster and held in a scratch file outside the repository.

## Required follow-up
1. Credential owner rotates `webdesk_integration_owner` on every cluster where it is valid, then confirms with the new value.
2. Credential owner checks the cluster audit logs for logins with the old value since 3 November 2026 (time of exposure).
3. Engineering confirms the old value fails, by a login attempt that the owner approves.
4. Close this record only with the owner's written confirmation.
