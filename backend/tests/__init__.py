"""
Test suite for the collaborative LaTeX editor versioning system.

Covers:
- Unit tests for VersioningService methods
- Integration tests for complete workflows
- Concurrency tests for race condition resilience
- API endpoint tests with TestClient
- Edge cases and error handling
"""

__all__ = [
    "test_versioning",
    "conftest",
]
