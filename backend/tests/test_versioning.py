"""Tests for document versioning behavior."""

import pytest
import asyncio
from uuid import UUID

# Import after fixtures are defined in conftest.py
pytest_plugins = ("pytest_asyncio",)


class TestVersioningServiceUnit:
    """Unit tests for VersioningService core functionality."""

    @pytest.mark.asyncio
    async def test_get_or_create_document_creates_new(self, versioning_service):
        """Test that get_or_create_document creates a new document."""
        result = await versioning_service.get_or_create_document("doc_abc123", "Test Document")
        assert isinstance(result, UUID)

    @pytest.mark.asyncio
    async def test_get_or_create_document_idempotent(self, versioning_service):
        """Test that repeated calls return same UUID (idempotent)."""
        doc_id1 = await versioning_service.get_or_create_document("doc_identical", "Test Doc")
        doc_id2 = await versioning_service.get_or_create_document("doc_identical", "Test Doc")
        assert doc_id1 == doc_id2

    @pytest.mark.asyncio
    async def test_create_version_increments_version_number(self, versioning_service):
        """Test that version numbers increment sequentially."""
        doc_uuid = await versioning_service.get_or_create_document("doc_increment", "Increment Test")
        
        version_id1, version_num1 = await versioning_service.create_version(doc_uuid, "content1")
        version_id2, version_num2 = await versioning_service.create_version(doc_uuid, "content2")
        
        assert version_num1 == 1
        assert version_num2 == 2
        assert isinstance(version_id1, UUID)
        assert isinstance(version_id2, UUID)
        assert version_id1 != version_id2

    @pytest.mark.asyncio
    async def test_create_version_with_empty_content(self, versioning_service):
        """Test creating a version with empty content."""
        doc_uuid = await versioning_service.get_or_create_document("doc_empty", "Empty Test")
        
        version_id, version_num = await versioning_service.create_version(doc_uuid, "")
        assert version_num == 1
        
        version = await versioning_service.get_version_by_number(doc_uuid, 1)
        assert version is not None
        assert version["content"] == ""

    @pytest.mark.asyncio
    async def test_create_version_with_large_content(self, versioning_service):
        """Test creating a version with large content (< 1MB)."""
        doc_uuid = await versioning_service.get_or_create_document("doc_large", "Large Content Test")
        
        large_content = "x" * 500000  # 500KB
        version_id, version_num = await versioning_service.create_version(doc_uuid, large_content)
        
        assert version_num == 1
        retrieved = await versioning_service.get_version_by_number(doc_uuid, 1)
        assert retrieved["content"] == large_content

    @pytest.mark.asyncio
    async def test_get_latest_version_empty_document(self, versioning_service):
        """Test get_latest_version returns None for document with no versions."""
        doc_uuid = await versioning_service.get_or_create_document("doc_no_versions", "No Versions")
        
        version = await versioning_service.get_latest_version(doc_uuid)
        assert version is None

    @pytest.mark.asyncio
    async def test_get_version_by_number_not_found(self, versioning_service):
        """Test that requesting non-existent version returns None."""
        doc_uuid = await versioning_service.get_or_create_document("doc_not_found", "Not Found Test")
        
        version = await versioning_service.get_version_by_number(doc_uuid, 999)
        assert version is None


class TestVersioningServiceIntegration:
    """Integration tests for complete versioning workflows."""

    @pytest.mark.asyncio
    async def test_complete_save_and_retrieve_flow(self, versioning_service):
        """Test complete flow: save version -> retrieve -> verify content."""
        doc_uuid = await versioning_service.get_or_create_document("doc_flow", "Flow Test")
        
        version_id1, num1 = await versioning_service.create_version(doc_uuid, "Version 1 content")
        version_id2, num2 = await versioning_service.create_version(doc_uuid, "Version 2 content")
        
        v1 = await versioning_service.get_version_by_number(doc_uuid, 1)
        assert v1 is not None
        assert v1["content"] == "Version 1 content"
        assert v1["version_number"] == 1
        
        v2 = await versioning_service.get_version_by_number(doc_uuid, 2)
        assert v2 is not None
        assert v2["content"] == "Version 2 content"
        assert v2["version_number"] == 2

    @pytest.mark.asyncio
    async def test_version_history_pagination(self, versioning_service):
        """Test paginated version history retrieval."""
        doc_uuid = await versioning_service.get_or_create_document("doc_pagination", "Pagination Test")
        
        # Create 50 versions
        for i in range(50):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        # Get page 1 (20 items default)
        versions_p1, total = await versioning_service.get_version_history(doc_uuid, page=1, page_size=20)
        assert len(versions_p1) == 20
        assert total == 50
        
        # Get page 3 (10 items remaining)
        versions_p3, total = await versioning_service.get_version_history(doc_uuid, page=3, page_size=20)
        assert len(versions_p3) == 10
        assert total == 50

    @pytest.mark.asyncio
    async def test_version_history_ordering(self, versioning_service):
        """Test that version history returns versions in correct order (newest first)."""
        doc_uuid = await versioning_service.get_or_create_document("doc_ordering", "Ordering Test")
        
        for i in range(1, 6):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        versions, _ = await versioning_service.get_version_history(doc_uuid, page=1, page_size=10)
        version_numbers = [v["version_number"] for v in versions]
        assert version_numbers == [5, 4, 3, 2, 1]  # Newest first

    @pytest.mark.asyncio
    async def test_latest_version_retrieval(self, versioning_service):
        """Test fetching latest version returns most recent."""
        doc_uuid = await versioning_service.get_or_create_document("doc_latest", "Latest Test")
        
        await versioning_service.create_version(doc_uuid, "Content 1")
        await versioning_service.create_version(doc_uuid, "Content 2")
        await versioning_service.create_version(doc_uuid, "Content 3")
        
        latest = await versioning_service.get_latest_version(doc_uuid)
        assert latest is not None
        assert latest["version_number"] == 3
        assert latest["content"] == "Content 3"


class TestVersioningServiceConcurrency:
    """Test concurrent version creation (race condition resilience)."""

    @pytest.mark.asyncio
    async def test_concurrent_version_creation_no_gap_in_numbers(self, versioning_service):
        """Test that concurrent creates don't create gaps in version numbers."""
        doc_uuid = await versioning_service.get_or_create_document("doc_concurrent", "Concurrent Test")
        
        # Create 10 versions concurrently
        tasks = [
            versioning_service.create_version(doc_uuid, f"Content {i}")
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        
        # Version numbers should be 1-10 with no gaps
        version_numbers = sorted([num for _, num in results])
        assert version_numbers == list(range(1, 11))

    @pytest.mark.asyncio
    async def test_concurrent_version_creation_no_duplicates(self, versioning_service):
        """Test that concurrent creates assign unique version numbers."""
        doc_uuid = await versioning_service.get_or_create_document("doc_duplicates", "Duplicates Test")
        
        tasks = [
            versioning_service.create_version(doc_uuid, f"Content {i}")
            for i in range(20)
        ]
        results = await asyncio.gather(*tasks)
        version_numbers = [num for _, num in results]
        
        assert len(version_numbers) == len(set(version_numbers))  # All unique
        assert set(version_numbers) == set(range(1, 21))

    @pytest.mark.asyncio
    async def test_concurrent_create_and_retrieve(self, versioning_service):
        """Test concurrent creates interleaved with retrieval."""
        doc_uuid = await versioning_service.get_or_create_document("doc_mixed", "Mixed Operations Test")
        
        # Start concurrent creates
        async def retrieve_after_delay():
            await asyncio.sleep(0.05)  # Let some creates complete
            return await versioning_service.get_latest_version(doc_uuid)
        
        create_tasks = [
            versioning_service.create_version(doc_uuid, f"Content {i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*create_tasks, retrieve_after_delay())
        # Should have created 10 versions successfully
        # Latest version should exist (may be None if called before any creates, but unlikely)
        assert len([r for r in results if isinstance(r, tuple)]) == 10


class TestVersioningServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self, versioning_service):
        """Test that special characters preserved in content."""
        doc_uuid = await versioning_service.get_or_create_document("doc_special", "Special Chars Test")
        
        content = "Special: ñ, 中文, emoji 🚀, tabs\t, newlines\n"
        version_id, num = await versioning_service.create_version(doc_uuid, content)
        
        retrieved = await versioning_service.get_version_by_number(doc_uuid, num)
        assert retrieved is not None
        assert retrieved["content"] == content

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, versioning_service):
        """Test Unicode content is properly stored and retrieved."""
        doc_uuid = await versioning_service.get_or_create_document("doc_unicode", "Unicode Test")
        
        contents = [
            "English content",
            "Контент на русском",
            "日本語のコンテンツ",
            "محتوى باللغة العربية",
        ]
        
        for content in contents:
            version_id, num = await versioning_service.create_version(doc_uuid, content)
            retrieved = await versioning_service.get_version_by_number(doc_uuid, num)
            assert retrieved is not None
            assert retrieved["content"] == content

    @pytest.mark.asyncio
    async def test_pagination_first_page(self, versioning_service):
        """Test pagination boundary: first page."""
        doc_uuid = await versioning_service.get_or_create_document("doc_page_first", "First Page Test")
        
        for i in range(25):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        versions, total = await versioning_service.get_version_history(doc_uuid, page=1, page_size=10)
        assert len(versions) == 10
        assert total == 25
        assert versions[0]["version_number"] == 25  # Newest first

    @pytest.mark.asyncio
    async def test_pagination_last_page(self, versioning_service):
        """Test pagination boundary: last page with fewer items."""
        doc_uuid = await versioning_service.get_or_create_document("doc_page_last", "Last Page Test")
        
        for i in range(25):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        versions, total = await versioning_service.get_version_history(doc_uuid, page=3, page_size=10)
        assert len(versions) == 5
        assert total == 25

    @pytest.mark.asyncio
    async def test_pagination_beyond_total(self, versioning_service):
        """Test pagination with page beyond available data."""
        doc_uuid = await versioning_service.get_or_create_document("doc_page_beyond", "Beyond Test")
        
        for i in range(10):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        versions, total = await versioning_service.get_version_history(doc_uuid, page=100, page_size=10)
        assert len(versions) == 0
        assert total == 10

    @pytest.mark.asyncio
    async def test_max_page_size(self, versioning_service):
        """Test pagination with maximum page size (100)."""
        doc_uuid = await versioning_service.get_or_create_document("doc_max_page", "Max Page Test")
        
        for i in range(50):
            await versioning_service.create_version(doc_uuid, f"Content {i}")
        
        versions, total = await versioning_service.get_version_history(doc_uuid, page=1, page_size=100)
        assert len(versions) == 50
        assert total == 50


class TestVersioningAPIEndpoints:
    """Test API endpoints using FastAPI TestClient."""

    def test_save_version_endpoint_success(self, client):
        """Test POST /api/documents/{doc_id}/versions creates version."""
        response = client.post(
            "/api/documents/test_doc_1/versions",
            json={"content": "Test content"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "version_id" in data
        assert data["version_number"] == 1
        assert data["document_id"]

    def test_save_version_endpoint_multiple_saves(self, client):
        """Test multiple version saves increment version number."""
        doc_id = "test_multi_save"
        
        # First save
        response1 = client.post(
            f"/api/documents/{doc_id}/versions",
            json={"content": "Content 1"}
        )
        assert response1.status_code == 201
        assert response1.json()["version_number"] == 1
        
        # Second save
        response2 = client.post(
            f"/api/documents/{doc_id}/versions",
            json={"content": "Content 2"}
        )
        assert response2.status_code == 201
        assert response2.json()["version_number"] == 2

    def test_save_version_endpoint_invalid_content(self, client):
        """Test POST endpoint with invalid content raises error."""
        response = client.post(
            "/api/documents/test_doc/versions",
            json={}  # Missing required 'content' field
        )
        assert response.status_code == 422  # Validation error

    def test_get_version_history_endpoint(self, client):
        """Test GET /api/documents/{doc_id}/versions returns paginated history."""
        doc_id = "test_history_doc"
        
        # Create some versions first
        for i in range(25):
            client.post(
                f"/api/documents/{doc_id}/versions",
                json={"content": f"Content {i}"}
            )
        
        response = client.get(f"/api/documents/{doc_id}/versions?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["total_pages"] == 3

    def test_get_version_history_second_page(self, client):
        """Test pagination second page retrieval."""
        doc_id = "test_history_page2"
        
        # Create 25 versions
        for i in range(25):
            client.post(
                f"/api/documents/{doc_id}/versions",
                json={"content": f"Content {i}"}
            )
        
        response = client.get(f"/api/documents/{doc_id}/versions?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 10
        assert data["page"] == 2
        assert data["has_next"] == True
        assert data["has_previous"] == True

    def test_get_latest_version_endpoint(self, client):
        """Test GET /api/documents/{doc_id}/versions/latest."""
        doc_id = "test_latest_endpoint"
        
        client.post(f"/api/documents/{doc_id}/versions", json={"content": "V1"})
        client.post(f"/api/documents/{doc_id}/versions", json={"content": "V2"})
        
        response = client.get(f"/api/documents/{doc_id}/versions/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 2
        assert data["content"] == "V2"

    def test_get_specific_version_endpoint(self, client):
        """Test GET /api/documents/{doc_id}/versions/{version_number}."""
        doc_id = "test_specific_version"
        
        for i in range(1, 4):
            client.post(
                f"/api/documents/{doc_id}/versions",
                json={"content": f"Content {i}"}
            )
        
        response = client.get(f"/api/documents/{doc_id}/versions/2")
        assert response.status_code == 200
        data = response.json()
        assert data["version_number"] == 2
        assert data["content"] == "Content 2"

    def test_get_version_not_found(self, client):
        """Test 404 when requesting non-existent version."""
        response = client.get("/api/documents/nonexistent/versions/999")
        assert response.status_code == 404

    def test_pagination_default_page_size(self, client):
        """Test default page size when not specified."""
        doc_id = "test_default_page_size"
        
        for i in range(50):
            client.post(
                f"/api/documents/{doc_id}/versions",
                json={"content": f"Content {i}"}
            )
        
        response = client.get(f"/api/documents/{doc_id}/versions")
        assert response.status_code == 200
        data = response.json()
        # Default page size should be 20
        assert len(data["versions"]) == 20

    def test_pagination_exceeds_max_page_size(self, client):
        """Test that exceeding max page_size returns error."""
        response = client.get("/api/documents/test/versions?page_size=101")
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    # Run tests with: pytest tests/test_versioning.py -v
    # Run specific test class: pytest tests/test_versioning.py::TestVersioningServiceUnit -v
    # Run with coverage: pytest tests/test_versioning.py --cov=services --cov=routes
    pytest.main([__file__, "-v", "--tb=short"])

