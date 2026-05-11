"""
pytest configuration and fixtures for xai-faf-rag tests.

This module sets up mock xai_sdk module before any tests import the integrator,
allowing tests to run without the actual xai-sdk installed.
"""

import sys
from unittest.mock import MagicMock, Mock


# Create mock xai_sdk module and its components
mock_xai_sdk = MagicMock()

# Create exception classes that can be instantiated properly
class MockAuthenticationError(Exception):
    """Mock AuthenticationError for testing."""
    pass


class MockRateLimitError(Exception):
    """Mock RateLimitError for testing."""
    pass


class MockAPIError(Exception):
    """Mock APIError for testing."""
    def __init__(self, message="API Error", status_code=500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Create a mock Client class that can be instantiated
class MockClient:
    """Mock Client class for testing."""
    _instance = None
    _collections = None
    _chat = None
    _init_error = None  # Set to exception class to raise on init

    def __init__(self, api_key=None, management_api_key=None):
        if MockClient._init_error:
            error = MockClient._init_error
            MockClient._init_error = None  # Reset after raising
            raise error
        self.api_key = api_key
        self.management_api_key = management_api_key
        MockClient._instance = self

    @property
    def collections(self):
        if MockClient._collections is None:
            MockClient._collections = MagicMock()
        return MockClient._collections

    @property
    def chat(self):
        if MockClient._chat is None:
            MockClient._chat = MagicMock()
        return MockClient._chat

    @classmethod
    def reset_mock(cls):
        """Reset the mock state."""
        cls._instance = None
        cls._collections = None
        cls._chat = None
        cls._init_error = None


# Assign mock classes to module
mock_xai_sdk.AuthenticationError = MockAuthenticationError
mock_xai_sdk.RateLimitError = MockRateLimitError
mock_xai_sdk.APIError = MockAPIError
mock_xai_sdk.Client = MockClient

# Create mock xai_sdk.chat module
mock_chat_module = MagicMock()
mock_chat_module.user = lambda x: ("user", x)
mock_chat_module.system = lambda x: ("system", x)
mock_xai_sdk.chat = mock_chat_module

# Create mock xai_sdk.tools module
mock_tools_module = MagicMock()
mock_tools_module.collections_search = lambda **kwargs: {"tool": "collections_search", **kwargs}
mock_xai_sdk.tools = mock_tools_module

# Insert mock into sys.modules BEFORE any other imports
sys.modules['xai_sdk'] = mock_xai_sdk
sys.modules['xai_sdk.chat'] = mock_chat_module
sys.modules['xai_sdk.tools'] = mock_tools_module


import pytest
import os


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables and mocks before/after each test."""
    # Store original values
    orig_api_key = os.environ.get("XAI_API_KEY")
    orig_mgmt_key = os.environ.get("XAI_MANAGEMENT_API_KEY")

    # Reset mock state before each test
    MockClient.reset_mock()

    yield

    # Restore original values
    if orig_api_key:
        os.environ["XAI_API_KEY"] = orig_api_key
    else:
        os.environ.pop("XAI_API_KEY", None)

    if orig_mgmt_key:
        os.environ["XAI_MANAGEMENT_API_KEY"] = orig_mgmt_key
    else:
        os.environ.pop("XAI_MANAGEMENT_API_KEY", None)


@pytest.fixture
def mock_client():
    """Provide a configured mock xAI client."""
    # Reset before providing a fresh client
    MockClient.reset_mock()

    # Set up default mock behavior
    mock_collection = MagicMock()
    mock_collection.collection_id = "test_coll_id"
    mock_collection.name = "Test Collection"

    MockClient._collections = MagicMock()
    MockClient._collections.list.return_value.data = []
    MockClient._collections.create.return_value = mock_collection
    MockClient._collections.search.return_value = []

    MockClient._chat = MagicMock()
    mock_chat_response = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Test response"
    mock_chat_response.sample.return_value = mock_response
    MockClient._chat.create.return_value = mock_chat_response

    # Create and return the client
    os.environ["XAI_API_KEY"] = "test_key"
    os.environ["XAI_MANAGEMENT_API_KEY"] = "test_mgmt"

    from xai_sdk import Client
    return Client(api_key="test_key", management_api_key="test_mgmt")
