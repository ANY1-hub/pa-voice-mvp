# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- UUID strict validation for `X-User-Id` header (must be valid UUID, else 401)
- Minimal memory consolidation:
  - Promotion of high-importance Working Memory items (≥ 0.7) to Semantic Memory
  - Cleanup of old + low-importance Semantic facts (< 0.25 and > 30 days)
  - Exact-content deduplication in Semantic Memory
- Structured extension points in `consolidate()` for later entity linking and drift detection
- Tests for consolidation logic (`tests/test_consolidation.py`)
- Updated memory design documentation

## [0.1.0] - 2026-07-16

### Added
- Project initialization
- Basic README and project structure
- Security & Quality standards defined (ISO alignment)
