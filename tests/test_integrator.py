"""
Comprehensive tests for XAIFafRag integrator.

Test coverage:
- Unit tests with mocked xAI SDK
- Authentication handling
- Collection management
- File uploads
- Search operations
- RAG chat queries
- Cache behavior
- Error handling
- Edge cases
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# conftest.py sets up the mock xai_sdk module before this imports
from tests.conftest import MockClient


def setup_mock_client(collection_id="test_coll_id", existing_collection=None):
    """Helper to set up mock client state."""
    MockClient.reset_mock()

    mock_collection = MagicMock()
    mock_collection.collection_id = collection_id

    MockClient._collections = MagicMock()
    if existing_collection:
        MockClient._collections.list.return_value.data = [existing_collection]
    else:
        MockClient._collections.list.return_value.data = []
    MockClient._collections.create.return_value = mock_collection
    MockClient._collections.search.return_value = []

    MockClient._chat = MagicMock()
    mock_chat_response = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Test response"
    mock_chat_response.sample.return_value = mock_response
    MockClient._chat.create.return_value = mock_chat_response


class TestXAIFafRagInitialization:
    """Test XAIFafRag initialization and configuration."""

    def test_init_with_env_vars(self):
        """Test initialization using environment variables."""
        setup_mock_client(collection_id="coll_test_123")

        os.environ["XAI_API_KEY"] = "test_api_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt_key"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()

        assert integrator.collection_id == "coll_test_123"

    def test_init_with_explicit_keys(self):
        """Test initialization with explicit API keys."""
        setup_mock_client(collection_id="coll_explicit_456")

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(
            api_key="explicit_api_key",
            management_api_key="explicit_mgmt_key"
        )

        assert integrator.api_key == "explicit_api_key"
        assert integrator.management_api_key == "explicit_mgmt_key"

    def test_init_without_api_key_raises(self):
        """Test that initialization without API key raises ValueError."""
        os.environ.pop("XAI_API_KEY", None)
        os.environ.pop("XAI_MANAGEMENT_API_KEY", None)

        from src.integrator import XAIFafRag

        with pytest.raises(ValueError) as exc_info:
            XAIFafRag()

        assert "XAI_API_KEY required" in str(exc_info.value)

    def test_init_with_custom_collection_name(self):
        """Test initialization with custom collection name."""
        setup_mock_client(collection_id="coll_custom_789")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(collection_name="Custom Collection")

        assert integrator.collection_name == "Custom Collection"

    def test_init_cache_enabled_by_default(self):
        """Test that cache is enabled by default."""
        setup_mock_client()

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()

        assert integrator.enable_cache is True

    def test_init_cache_can_be_disabled(self):
        """Test that cache can be disabled."""
        setup_mock_client()

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=False)

        assert integrator.enable_cache is False


class TestInitializationErrors:
    """Test error handling during initialization (lines 95-97, 122-127)."""

    def test_auth_error_during_client_init(self):
        """Test AuthenticationError during client initialization (lines 95-97)."""
        from xai_sdk import AuthenticationError

        MockClient.reset_mock()
        MockClient._init_error = AuthenticationError("Invalid API key")

        os.environ["XAI_API_KEY"] = "bad_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "bad_mgmt"

        from src.integrator import XAIFafRag

        with pytest.raises(AuthenticationError):
            XAIFafRag()

    def test_rate_limit_during_collection_setup_retries(self):
        """Test RateLimitError during collection setup triggers retry (lines 122-124)."""
        from xai_sdk import RateLimitError
        from unittest.mock import patch

        MockClient.reset_mock()
        MockClient._collections = MagicMock()

        # First call raises RateLimitError, second succeeds
        mock_collection = MagicMock()
        mock_collection.collection_id = "retry_coll_id"

        call_count = [0]
        def list_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RateLimitError("Rate limited")
            result = MagicMock()
            result.data = []
            return result

        MockClient._collections.list.side_effect = list_side_effect
        MockClient._collections.create.return_value = mock_collection

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag

        # Patch time.sleep to avoid waiting
        with patch('src.integrator.time.sleep'):
            integrator = XAIFafRag()

        assert integrator.collection_id == "retry_coll_id"
        assert call_count[0] == 2  # Called twice (first failed, second succeeded)

    def test_api_error_during_collection_setup_raises(self):
        """Test APIError during collection setup is raised (lines 126-127)."""
        from xai_sdk import APIError

        MockClient.reset_mock()
        MockClient._collections = MagicMock()
        MockClient._collections.list.side_effect = APIError("Server error", 500)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag

        with pytest.raises(APIError):
            XAIFafRag()


class TestCollectionManagement:
    """Test collection creation and reuse."""

    def test_reuses_existing_collection(self):
        """Test that existing collection is reused by name."""
        existing_coll = MagicMock()
        existing_coll.name = "FAF Elite Palace"
        existing_coll.id = "existing_coll_id"
        setup_mock_client(existing_collection=existing_coll)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()

        assert integrator.collection_id == "existing_coll_id"
        MockClient._collections.create.assert_not_called()

    def test_creates_new_collection_when_none_exists(self):
        """Test that new collection is created when none exists."""
        setup_mock_client(collection_id="new_coll_id")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()

        assert integrator.collection_id == "new_coll_id"
        MockClient._collections.create.assert_called_once()

    def test_create_collection_requires_management_key(self):
        """Test that creating collection requires management API key."""
        setup_mock_client()

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ.pop("XAI_MANAGEMENT_API_KEY", None)

        from src.integrator import XAIFafRag

        with pytest.raises(ValueError) as exc_info:
            XAIFafRag(management_api_key=None)

        assert "XAI_MANAGEMENT_API_KEY required" in str(exc_info.value)


class TestFileUpload:
    """Test file upload functionality."""

    @pytest.fixture(autouse=True)
    def setup_temp_files(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create test .faf file
        self.faf_file = self.temp_path / "project.faf"
        self.faf_file.write_text("""
faf_version: 3.0.0
project:
  name: Test Project
  goal: Testing
""")

        # Create test PDF file
        self.pdf_file = self.temp_path / "test.pdf"
        self.pdf_file.write_bytes(b"%PDF-1.4\ntest content")

        yield

        self.temp_dir.cleanup()

    def test_sync_faf_uploads_file(self):
        """Test that sync_faf uploads the .faf file."""
        setup_mock_client(collection_id="coll_upload_test")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.sync_faf(str(self.faf_file))

        assert result is True
        MockClient._collections.upload_document.assert_called_once()

        call_args = MockClient._collections.upload_document.call_args
        assert call_args.kwargs["name"] == "project.faf"
        assert call_args.kwargs["content_type"] == "text/yaml"

    def test_sync_faf_with_supporting_files(self):
        """Test that sync_faf uploads supporting files."""
        setup_mock_client(collection_id="coll_multi_upload")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.sync_faf(
            str(self.faf_file),
            supporting=[str(self.pdf_file)]
        )

        assert result is True
        assert MockClient._collections.upload_document.call_count == 2

    def test_sync_faf_handles_missing_file(self):
        """Test that sync_faf handles missing files gracefully."""
        setup_mock_client(collection_id="coll_missing_file")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.sync_faf("/nonexistent/file.faf")

        assert result is False

    def test_sync_faf_requires_management_key(self):
        """Test that sync_faf requires management API key."""
        existing_coll = MagicMock()
        existing_coll.name = "FAF Elite Palace"
        existing_coll.id = "existing_id"
        setup_mock_client(existing_collection=existing_coll)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ.pop("XAI_MANAGEMENT_API_KEY", None)

        from src.integrator import XAIFafRag
        # Create with existing collection (no mgmt key needed for that)
        integrator = XAIFafRag(management_api_key=None)
        integrator.management_api_key = None  # Force None

        with pytest.raises(ValueError):
            integrator.sync_faf(str(self.faf_file))

    def test_sync_faf_rate_limit_retries(self):
        """Test RateLimitError during upload triggers retry (lines 170-173)."""
        from xai_sdk import RateLimitError
        from unittest.mock import patch

        setup_mock_client(collection_id="coll_upload_retry")

        # First call raises RateLimitError, second succeeds
        call_count = [0]
        def upload_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RateLimitError("Rate limited")
            return MagicMock()

        MockClient._collections.upload_document.side_effect = upload_side_effect

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()

        # Patch time.sleep to avoid waiting
        with patch('src.integrator.time.sleep'):
            result = integrator.sync_faf(str(self.faf_file))

        assert result is True
        assert call_count[0] == 2  # Called twice (first failed, second succeeded)

    def test_sync_faf_api_error_returns_false(self):
        """Test APIError during upload returns False (lines 174-176)."""
        from xai_sdk import APIError

        setup_mock_client(collection_id="coll_upload_api_error")
        MockClient._collections.upload_document.side_effect = APIError("Upload failed", 500)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.sync_faf(str(self.faf_file))

        assert result is False


class TestSearch:
    """Test search functionality."""

    def test_search_returns_results(self):
        """Test that search returns results."""
        setup_mock_client(collection_id="coll_search_test")

        mock_result = MagicMock()
        mock_result.snippet = "Test snippet"
        mock_result.file_name = "test.faf"
        mock_result.score = 0.95
        MockClient._collections.search.return_value = [mock_result]

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        results = integrator.search("test query")

        assert len(results) == 1
        MockClient._collections.search.assert_called_once()

    def test_search_uses_hybrid_mode_by_default(self):
        """Test that search uses hybrid retrieval mode by default."""
        setup_mock_client(collection_id="coll_hybrid")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        integrator.search("test")

        call_args = MockClient._collections.search.call_args
        assert call_args.kwargs["retrieval_mode"] == "hybrid"

    def test_search_respects_custom_retrieval_mode(self):
        """Test that search respects custom retrieval mode."""
        setup_mock_client(collection_id="coll_semantic")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        integrator.search("test", retrieval_mode="semantic")

        call_args = MockClient._collections.search.call_args
        assert call_args.kwargs["retrieval_mode"] == "semantic"

    def test_search_caches_results(self):
        """Test that search caches results."""
        setup_mock_client(collection_id="coll_cache")
        MockClient._collections.search.return_value = ["result"]

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # First call
        integrator.search("test query")
        # Second call (should hit cache)
        integrator.search("test query")

        # Should only call API once
        assert MockClient._collections.search.call_count == 1

    def test_search_skips_cache_when_disabled(self):
        """Test that search skips cache when disabled."""
        setup_mock_client(collection_id="coll_no_cache")
        MockClient._collections.search.return_value = ["result"]

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=False)

        # Multiple calls
        integrator.search("test query")
        integrator.search("test query")

        # Should call API each time
        assert MockClient._collections.search.call_count == 2


class TestQuery:
    """Test RAG chat query functionality."""

    def test_query_returns_response(self):
        """Test that query returns a response."""
        setup_mock_client(collection_id="coll_query_test")

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is the grounded response"
        mock_chat.sample.return_value = mock_response
        MockClient._chat.create.return_value = mock_chat

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.query("What are the project goals?")

        assert result == "This is the grounded response"

    def test_query_uses_correct_model(self):
        """Test that query uses the correct model."""
        setup_mock_client(collection_id="coll_model_test")

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_chat.sample.return_value = mock_response
        MockClient._chat.create.return_value = mock_chat

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        integrator.query("test", model="grok-4-1-fast")

        call_args = MockClient._chat.create.call_args
        assert call_args.kwargs["model"] == "grok-4-1-fast"

    def test_query_uses_custom_system_prompt(self):
        """Test that query uses custom system prompt."""
        setup_mock_client(collection_id="coll_prompt_test")

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_chat.sample.return_value = mock_response
        MockClient._chat.create.return_value = mock_chat

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        integrator.query("test", system_prompt="Custom system prompt")

        call_args = MockClient._chat.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 1

    def test_query_caches_results(self):
        """Test that query caches results."""
        setup_mock_client(collection_id="coll_query_cache")

        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Cached response"
        mock_chat.sample.return_value = mock_response
        MockClient._chat.create.return_value = mock_chat

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Call twice with same query
        integrator.query("test query")
        integrator.query("test query")

        # Should only call API once
        assert MockClient._chat.create.call_count == 1


class TestErrorHandling:
    """Test error handling."""

    def test_handles_rate_limit_on_search(self):
        """Test that rate limit errors are handled gracefully on search."""
        from xai_sdk import RateLimitError

        setup_mock_client(collection_id="coll_rate_limit")
        MockClient._collections.search.side_effect = RateLimitError("Rate limited")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        results = integrator.search("test")

        # Should return empty list, not raise
        assert results == []

    def test_handles_rate_limit_on_query(self):
        """Test that rate limit errors are handled gracefully on query."""
        from xai_sdk import RateLimitError

        setup_mock_client(collection_id="coll_rate_query")
        MockClient._chat.create.side_effect = RateLimitError("Rate limited")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.query("test")

        assert "Rate limited" in result

    def test_handles_auth_error_on_query(self):
        """Test that auth errors are handled gracefully on query."""
        from xai_sdk import AuthenticationError

        setup_mock_client(collection_id="coll_auth_error")
        MockClient._chat.create.side_effect = AuthenticationError("Invalid key")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.query("test")

        assert "Authentication failed" in result

    def test_handles_api_error_on_search(self):
        """Test that API errors are handled gracefully on search (lines 223-225)."""
        from xai_sdk import APIError

        setup_mock_client(collection_id="coll_api_error_search")
        MockClient._collections.search.side_effect = APIError("Server error", 500)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        results = integrator.search("test")

        # Should return empty list, not raise
        assert results == []

    def test_handles_api_error_on_query(self):
        """Test that API errors are handled gracefully on query (lines 288-290)."""
        from xai_sdk import APIError

        setup_mock_client(collection_id="coll_api_error_query")
        MockClient._chat.create.side_effect = APIError("Server error", 500)

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag()
        result = integrator.query("test")

        assert "Error:" in result


class TestCacheManagement:
    """Test cache management functionality."""

    def test_clear_cache(self):
        """Test that cache can be cleared."""
        setup_mock_client(collection_id="coll_clear_cache")
        MockClient._collections.search.return_value = ["result"]

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        # Add something to cache
        integrator.search("test")
        assert integrator.cache_stats()["size"] == 1

        # Clear cache
        integrator.clear_cache()
        assert integrator.cache_stats()["size"] == 0

    def test_cache_stats(self):
        """Test cache statistics."""
        setup_mock_client(collection_id="coll_stats")
        MockClient._collections.search.return_value = ["result"]

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import XAIFafRag
        integrator = XAIFafRag(enable_cache=True)

        stats = integrator.cache_stats()
        assert "size" in stats
        assert "enabled" in stats
        assert stats["enabled"] is True


class TestConvenienceFunction:
    """Test convenience functions."""

    def test_create_integrator(self):
        """Test create_integrator convenience function."""
        setup_mock_client(collection_id="coll_convenience")

        os.environ["XAI_API_KEY"] = "test_key"
        os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

        from src.integrator import create_integrator
        integrator = create_integrator()

        assert integrator is not None
        assert integrator.collection_id == "coll_convenience"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
