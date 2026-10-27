"""Resource limits for document parsing (Phase 4, H-31).

The values are proposals under H-DEC-3 and await WDS selection. They are constants so that any
change is visible in review. Each breach fails the version with the stable class named here; a
breach never produces partial text.
"""

from __future__ import annotations

MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_RATIO = 100
MAX_SEGMENTS_PER_VERSION = 5000
MAX_CHARS_PER_SEGMENT = 20000

INPUT_TOO_LARGE = "input_too_large"
PDF_PAGE_LIMIT = "pdf_page_limit"
ARCHIVE_SIZE_LIMIT = "archive_size_limit"
ARCHIVE_RATIO_LIMIT = "archive_ratio_limit"
SEGMENT_LIMIT = "segment_limit"
SEGMENT_LENGTH_LIMIT = "segment_length_limit"
PYTHON_CONTROL = {INPUT_TOO_LARGE, PDF_PAGE_LIMIT, ARCHIVE_SIZE_LIMIT, ARCHIVE_RATIO_LIMIT}
