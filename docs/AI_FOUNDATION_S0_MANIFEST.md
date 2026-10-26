# AI–Foundation S0 baseline manifest

**S0 is the clean, committed Git commit `82585db`** (branch `feature/increment-1-foundation`). The baseline was taken from that
commit, not from a working tree. At the time of the baseline the working tree was clean (no modified or untracked files).

| Item | Value |
|---|---|
| S0 commit (full) | `82585dbd21af66cf922e2e52c6dee7e8a7c29aa3` |
| S0 tree | `2e2233477c5f89b85584f5bf04eef6d3e6dfb21e` |
| S0 archive (`git archive --format=tar 82585db`) | 2,027,520 bytes |
| S0 archive SHA-256 | `2a4d1056eb0293c16e6553ace7572b338c23e197619a6cc695a03d4cc425810b` |
| S0 `docs/GOVERNANCE_DECISION_REGISTER.md` SHA-256 | `0ca96f9e31e9b1074966d041c5bfac6393d41c218468256d489171b5bb785cce` |
| S0 `docs/PRODUCTION_BOUNDARY.md` SHA-256 | `284557df20f0a4f1c881de65ce58f3bd85780099b4fef4df61845e487f2b9e4c` |
| S0 `docs/AI_ACCESS_CONTRACT_PROPOSAL_v0.1.md` SHA-256 (historical proposal, unchanged) | `33f27f93525f10c6a7503a1ec58c8af3fed6d1121cc7e9390ed6f70b54f63fdf` |

Verification of S0 (recomputed from `git show` and `git archive` of `82585db`, not from the working tree).

## Artifacts introduced after S0 (this increment)

| Artifact | SHA-256 |
|---|---|
| `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` (approved contract `ai-read/v1`) | `8f2617c1039bb5bdcd974bf09f54c39137b17018f663936c2f7887c08b7aac2f` |
| `docs/RUFF_FORMAT_EXCEPTIONS.md` | `074ab590787f047e9b4cd8e301ec4060499d25db39f737c03af8efcc364e3333` |

The contract hash is of the committed file. Any change to the contract changes the hash, and the contract's version is then
reissued (section 13 of the contract).

## Migration baseline

- S0 migration head: `0040_last_administrator_lock`.
- This increment adds `0041_ai_read_v1` (additive). Revisions 0001 to 0040 are unchanged in this increment, and their executed
  SQL is verified identical to their committed text (see `docs/INCREMENT_3_EVIDENCE.md`).
