"""Resource limits and isolation settings for document parsing (Phase 4, H-31 and H-32).

The numeric values are proposals under H-DEC-3 and await WDS selection. They are constants so that
any change is visible in review. Each breach fails the version with the stable class named here; a
breach never produces partial text.

``PARSER_TIMEOUT_SECONDS`` must stay below the Phase 3 job lease (120 s; not merged on this
branch, see docs/PHASE4_DEPENDENCY_REGISTER.md) so that a parser cannot outlive its claim.
``MEMORY_CAP_ENFORCED`` records the platform fact behind H-DEC-4: the address-space cap applies on
POSIX only. On Windows the process timeout and the file-size pre-check are the only enforced bounds
(approved for non-production under P4-GOV-2026-10-28; a separate decision is needed for production).
"""

from __future__ import annotations

import sys

MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_PDF_PAGE_STREAM_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_RATIO = 100
MAX_DOCX_ELEMENTS = 20000
MAX_SEGMENTS_PER_VERSION = 5000
MAX_CHARS_PER_SEGMENT = 20000

PARSER_TIMEOUT_SECONDS = 30
PARSER_OUTPUT_BYTES = 32 * 1024 * 1024
PARSER_MEMORY_BYTES = 1024 * 1024 * 1024
MEMORY_CAP_ENFORCED = sys.platform != "win32"

INPUT_TOO_LARGE = "input_too_large"
PDF_PAGE_LIMIT = "pdf_page_limit"
PDF_STREAM_LIMIT = "pdf_stream_limit"
ARCHIVE_SIZE_LIMIT = "archive_size_limit"
ARCHIVE_RATIO_LIMIT = "archive_ratio_limit"
DOCX_ELEMENT_LIMIT = "docx_element_limit"
SEGMENT_LIMIT = "segment_limit"
SEGMENT_LENGTH_LIMIT = "segment_length_limit"
PARSER_TIMEOUT = "parser_timeout"
PARSER_CRASH = "parser_crash"
PARSER_OUTPUT_LIMIT = "parser_output_limit"
PYTHON_CONTROL = {INPUT_TOO_LARGE, PDF_PAGE_LIMIT, ARCHIVE_SIZE_LIMIT, ARCHIVE_RATIO_LIMIT}
