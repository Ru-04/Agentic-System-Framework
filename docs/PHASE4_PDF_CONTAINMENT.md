# Phase 4 PDF containment: design, threat model and guarantees

Scope: the PDF path of Foundation Phase 4 (H-31, H-32, QA-05, QA-06). Commits: `d5dc287` (metered boundary and
nested-graph walk), `17c825b` (committed tests), `f03698d` (decoder lock). This document states what the implementation
guarantees and what it does not. It is engineering evidence, not WDS acceptance.

## 1. Threat

A PDF can be small on disk and large when decoded. Attacker-controlled streams can sit in any place the reader decodes:
cross-reference streams and object streams (decoded while the reader opens the file), page content, form XObjects,
tiling patterns, Type 3 glyph procedures and annotation appearance streams. The reader decodes them lazily and in a
different order from any code that inspects the raw bytes. A check that inspects raw bytes can therefore disagree with
the reader about where a stream begins and ends.

Reproduced on `05dbdca` (QA-05 re-test, synthetic, bounded):

| Variant | File | Decoded | Outcome on baseline |
|---|---|---|---|
| Object stream, standard | 61 611 B | 60 MiB | refused after ~137 MiB traced peak |
| Object stream, CR-only line ending after `stream` | 61 623 B | 60 MiB | not refused; decoded by reader |
| Object stream, literal `endstream` in deflate data | 61 516 B | 60 MiB | not refused by pre-scan; decoded by reader |

## 2. Root cause

The pre-scan (`_check_pdf_expansion`, commit `8d5b039`) located streams with `stream\r?\n` and `endstream`. The reader
locates them from the object table and from `/Length`, which the pre-scan did not use. Any disagreement, such as a CR-only
line ending or a delimiter-like sequence inside compressed data, left the reader free to decode what the pre-scan had not
measured. Matching the reader's parser was never going to be complete, so the pre-scan was the wrong boundary.

## 3. Enforcement boundary (current design)

The boundary is the decoder the reader calls, not the byte stream.

- pypdf routes every stream decode through `decode_stream_data`, which calls `FlateDecode.decode`,
  `LZWDecode._decodeb`, `RunLengthDecode.decode`, `DCTDecode.decode`, `JPXDecode.decode` and `CCITTFaxDecode.decode` by
  class attribute at call time (verified in pypdf 5.1.0, `pypdf/filters.py`). Every decode, for every stream type, reaches
  one of these.
- `_metered_pdf_decoding` replaces the flate decoder with a wrapper that first charges the compressed buffer to a
  per-parse `_DecodeMeter`, then calls the original decoder. The other decoders listed above are replaced with a refusal.
  The replacement is restored in a `finally` block.
- The meter inflates each distinct compressed buffer (charged once, keyed by object identity) with an output bound equal to
  the remaining budget plus one byte. It refuses when the cumulative decoded total would exceed either
  `MAX_ARCHIVE_UNCOMPRESSED_BYTES` (100 MiB) or `MAX_ARCHIVE_RATIO` (100) times the file size. A refusal is recorded on the
  meter and survives any internal retry by pypdf (pypdf may swallow an exception while it rebuilds the cross-reference
  table).
- Upload admission (`validation._check_pdf`) calls `open_pdf_structure`, which opens the file under the same meter. A
  refused expansion is returned as 422 with the same reason, before any source version exists.
- Parsing runs in a child process (H-32). The child timeout (30 s), output cap (32 MiB) and environment allowlist are
  unchanged.
- The decoder patch is process-wide. Opens are serialized by a re-entrant lock (`_PDF_DECODE_LOCK`), so a concurrent API
  request cannot observe another meter. A regression test covers this.

Because the bound is on the bytes the decoder produces, it does not depend on how the stream is delimited. CR-only
endings, CRLF, a literal `endstream` in compressed data, an indirect or wrong `/Length`, object streams, cross-reference
streams, and filter chains that include FlateDecode are all charged on the same path.

## 4. Nested-graph completeness (QA-06)

pypdf's `extract_text` does not follow form XObjects, annotation appearances, tiling patterns or Type 3 glyph procedures.
Their text would otherwise be lost silently.

`_page_has_hidden_text` walks the page's reachable graph:

- resources of the page: XObjects of subtype Form, tiling patterns, Type 3 fonts (`CharProcs`);
- the resources of each of those, recursively;
- annotation appearance streams (`/AP /N`, a stream or a dictionary of states).

A visited set (by object identity) makes cyclic references terminate. The walk is bounded to depth 8 and 512 objects. A
text block (`BT` as a whole token) found anywhere in the graph flags the page. A walk that cannot complete, or a stream
that cannot be decoded, also flags the page. A vector-only form is not flagged (negative control in the tests).

The result follows the approved classification:

- text extracted and nothing flagged: `succeeded`;
- text extracted and a flag: `partial` (one or more segments plus flagged regions);
- no committed segment and a flag or an image-only page: `unsupported`, with the region kept as
  `unextractable_regions` metadata;
- a whole-file refusal (size, ratio, unsupported filter on the reader's own structures, corrupt): `failed`.

## 5. Guarantees

Within the parser process, for an input that is accepted:

- The total decoded size produced by flate decoding across all streams a parse touches is at most 100 MiB, and at most
  100 times the file size. A refusal occurs before the refused bytes are returned to the reader.
- Each compressed buffer is inflated at most once for accounting. Repeated reads of the same stream are not charged again.
- LZW, RunLength, DCT, JPX and CCITT streams are never decoded. A stream the reader asks to decode with one of these
  refuses the page, or the file when the reader needs it to open.
- Upload admission applies the same bound before a source version is created.
- Per-page content is additionally bounded at 10 MiB decoded (H-31).
- The child process is bounded by a 30 s wall-clock timeout and a 32 MiB output cap (H-32).

## 6. Residual limitations (not contained)

- **Process memory on Windows (H-DEC-4): not established.** The bound is on decoded bytes, not on process memory. Python
  object overhead, pypdf's own structures and the input buffer are outside the bound. On Windows the child has no
  address-space cap. The worst case the bound permits (100 MiB decoded) has not been measured for process memory. Do not
  describe the containment as memory containment.
- **Time.** Bounded only by the 30 s child timeout on every platform, and by the 30 s wall-clock limit only in the child.
  Admission runs in the API process with no separate timeout; the same metered open is bounded by the decode budget but not
  by time. This is a known residual for admission.
- **Non-flate filters that expand.** ASCIIHex and ASCII85 can only shrink or halve their input, so they are not metered.
  Other filters are refused.
- **Corrupt flate data is refused.** The meter refuses a deflate stream that does not inflate (`corrupt_structure`). This
  is stricter than pypdf, which may tolerate a damaged stream. A PDF that pypdf reads with such a stream is rejected.
- **Process-wide patch.** The meter replaces decoder classes for the duration of one open. It is serialized within one
  process. Any other code in the same process that calls pypdf concurrently with a different expectation would observe the
  patch. The parser and admission are the only callers in this codebase.
- **Nested-form text is flagged, not extracted.** Option B (QA-06): the page is flagged. Text inside forms is not returned as
  segments. Source locators for such text do not exist.
- **Other unextracted content.** Images are not OCRed. Text that is drawn by an XObject of an unlisted kind, or that uses an
  unusual resource category, is not walked. Only the categories listed in section 4 are walked.

## 7. Supported and unsupported PDF structures (inventory)

| Structure | Parsed by pypdf | Decoded through meter | Behaviour in this parser |
|---|---|---|---|
| Classic cross-reference table | yes | no decode | supported |
| Cross-reference stream, FlateDecode, predictor | yes | yes | supported, metered |
| Object stream, FlateDecode | yes | yes, at object resolution | supported, metered |
| Page content, FlateDecode (array allowed) | yes | yes | supported, metered and per-page bounded |
| Page content, unfiltered | yes | no decode | supported |
| Form XObject (direct or nested) | yes | yes | walked for text; flagged if text |
| Tiling pattern stream | yes | yes | walked for text; flagged if text |
| Type 3 font CharProcs | yes | yes | walked for text; flagged if text |
| Annotation appearance stream | yes | yes | walked for text; flagged if text |
| Image XObject | yes | never decoded | not walked; flagged only through the image-only rule |
| LZWDecode, RunLengthDecode | yes | refused at decoder | page flagged, or file refused when needed to open |
| DCTDecode, JPXDecode, CCITTFaxDecode | yes | refused at decoder | page flagged when decoded |
| ASCIIHexDecode, ASCII85Decode | yes | not metered (cannot expand) | supported |
| Encrypted document | pypdf reports | not opened | refused: `encrypted_not_permitted` |
| Incremental update (second revision) | yes | every stream metered | supported, metered across revisions |
| CR, LF or CRLF after `stream` | yes | metered | supported, metered |
| Literal `endstream` inside compressed data | yes | metered | supported, metered |

## 8. Evidence

- Permanent tests: `tests/unit/test_pdf_containment.py` (QA-05 reproductions and variations, aggregate budget,
  LZW refusal, child-process containment, patch restoration, concurrency, QA-06 nested, cyclic, repeated, depth,
  siblings, vector control, annotations, Type 3, patterns).
- Committed-row tests: `tests/committed/test_parse_outcomes.py` (nested-form unsupported with metadata, mixed partial,
  admission refusal of an expanding cross-reference stream with HTTP-equivalent 422).
- Gate: see `docs/PHASE4_QA_REMEDIATION.md`, section 9.
