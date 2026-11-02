# Phase 4 synthetic demonstration output

Command: `pytest tests/committed/test_parse_demonstration.py -s -q`. Exit code 0. Identifiers vary per run; the stages and outcomes do not.

```text
[demo] 1. Upload: three synthetic sources through the real upload service
[demo]    uploaded notes.txt: version 2fdb75e7-32f5-4650-99b3-260f57dfbb8e (pending)
[demo]    uploaded scan.pdf: version f93f1c5c-b0f5-492c-84ab-245eed9c97bc (pending)
[demo]    uploaded table.docx: version 426b38a7-4603-480b-952d-4678d1d16621 (pending)
[demo] 2. Authorize: an analyst cannot obtain a reparse proof; an administrator can
[demo]    analyst reparse proof: refused by the authority (not issued)
[demo] 3. Isolate: the notes parse runs in a child process; a fault makes the child crash
[demo]    notes -> failed {'class': 'parser_crash'} (the worker process is still running)
[demo] 4. Persist segments: the scan parses with its image page flagged as a partial result
[demo]    scan -> partial, flagged ['pdf_page:2'], 1 segment kept
[demo] 5. Failure isolation: the DOCX parse succeeds with table cells, unaffected by the others
[demo]    table -> succeeded, 5 segments (one paragraph plus four table cells)
[demo] 6. Authorized reparse: the administrator reparses the crashed notes version
[demo]    reparse accepted: the notes version is pending again
[demo] 7. Retry: the notes version parses on the isolated path with no fault
[demo]    notes -> succeeded, 3 segments
[demo] 8. Reject stale operations: a spent proof and a stale source revision are refused
[demo]    replayed proof: refused (the proof was spent by the first accepted reparse)
[demo]    stale reparse of a succeeded version: refused (not_failed)
[demo] 9. Provenance: each TXT segment locates its text by character offsets
[demo]    line 1: characters 0-14
[demo]    line 3: characters 16-45
[demo]    line 4: characters 46-56
[demo] 10. Audit: the events recorded against the notes version
[demo]    source.upload.succeeded  outcome=success  class=-
[demo]    source.parse.failed  outcome=error  class=parser_crash
[demo]    source.reparse.succeeded  outcome=success  class=-
[demo]    source.parse.succeeded  outcome=success  class=-
[demo] Demonstration complete: every stage matched its expected result.
1 passed in 4.20s
```
