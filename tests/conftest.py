"""Test-wide settings."""

# tests/mpf_ported/ holds MPF's original test files, copied verbatim as references
# (expected wire traffic, configs, mock boards). They import MPF, so they never run.
collect_ignore_glob = ["mpf_ported/*/test_*.py"]
