# v0.3.3 Foundation mechanical validation

- Source baseline: v0.3.2, review dated 2026-10-16.
- Both registry and catalog YAML parse successfully.
- Explicit reference checks must consider all registry entries and tool IDs, not just services_and_tools. The earlier report's 12 unresolved references were incorrect: 11 false positives.
- Verified registry internal references (entries, services_and_tools, model_configuration and routing rule IDs): 0 unresolved ID references.
- One pre-existing later-phase activation value, `ROUTE-CROSS-PLATFORM-001.activate`, contains prose instead of an ID list. C-05 routing remains disabled and outside Gate 1.
- v0.3.3 contains EVAL-F01 through EVAL-F13 specifications, NOT passing implementation test results.
- EVAL-F10 fixture SHA-256: `5df52f543349fa88dd4a96d4f1f1f6183384adc754b477f65960b62e9b926da9`.
- All five normative Markdown spec headers and both YAML version fields updated to v0.3.3.
- Independent diff-focused Gate 1 review remains REQUIRED before Claude Code implementation.
