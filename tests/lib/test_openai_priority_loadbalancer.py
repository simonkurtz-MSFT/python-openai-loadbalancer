# pylint: disable=C0114,C0115,C0116,W0212,W0621

# Execute with "pytest -v" in the root directory

# https://docs.pytest.org/en/8.2.x/
# Reference test file for AzureOpenAI: https://github.com/kristapratico/openai-python/blob/main/tests/lib/test_azure.py

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import List
from unittest.mock import patch
from openai._models import FinalRequestOptions
from openai.lib.azure import AzureOpenAI, AsyncAzureOpenAI
import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import AsyncLoadBalancer, Backend, LoadBalancer  # pylint: disable=C0413

##########################################################################################################################################################

SKIP_LONG_RUNNING_TESTS = False

# Utility Functions

def create_async_client(backends: List[Backend]) -> AsyncAzureOpenAI:
    lb = AsyncLoadBalancer(backends)

    return AsyncAzureOpenAI(
        azure_endpoint = "https://foo.openai.azure.com",
        api_key = "example API key",
        api_version = "2024-04-01-preview",
        http_client = httpx.AsyncClient(transport = lb)
    )

def create_client(backends: List[Backend]) -> AzureOpenAI:
    lb = LoadBalancer(backends)

    return AzureOpenAI(
        azure_endpoint = "https://foo.openai.azure.com",
        api_key = "example API key",
        api_version = "2024-04-01-preview",
        http_client = httpx.Client(transport = lb)
    )

def create_final_request_options() -> FinalRequestOptions:
    return FinalRequestOptions.construct(
        method = "post",
        url = "completions",
        json_data = {"model": "my-deployment-model"},
    )

# Test Fixtures

# Backend Fixtures

# Factory fixture for backends
@pytest.fixture
def backends_factory():
    def _backends_factory(priority: int, is_throttling: bool, retry_after: int, path: str = None, api_key: str = None):
        # Start with a basic list of backends that will be modified depending on the passed arguments.
        backends: List[Backend] = [
            Backend("oai-eastus.openai.azure.com", 1),
            Backend("oai-southcentralus.openai.azure.com", 1),
            Backend("oai-westus.openai.azure.com", 1),
        ]

        for backend, _priority, throttling, secs, _path, _api_key in zip(backends, priority, is_throttling, retry_after, path, api_key):
            backend.is_throttling = throttling
            backend.priority = _priority

            if _api_key is not None:
                backend.api_key = _api_key

            if secs is not None:
                backend.retry_after = datetime.now(timezone.utc) + timedelta(seconds = secs)

            if _path is not None:
                backend.path = _path

        return backends

    return _backends_factory

@pytest.fixture
def backends_same_priority(backends_factory) -> List[Backend]:
    return backends_factory([1, 1, 1], [False, False, False], [None, None, None], [None, None, None], [None, None, None])

@pytest.fixture
def backends_same_priority_custom_paths(backends_factory) -> List[Backend]:
    return backends_factory([1, 1, 1], [False, False, False], [None, None, None], ["/ai", "ai/", "ai"], [None, None, None])

@pytest.fixture
def backends_same_priority_api_keys(backends_factory) -> List[Backend]:
    return backends_factory([1, 1, 1], [False, False, False], [None, None, None], [None, None, None], ["c3d116584360f9960b38cccc5f44caba", "21c14252762502e8fc78b61e21db114f", "d6370785453b2b9c331a94cb1b7aaa36"])

@pytest.fixture
def backends_tiered_priority(backends_factory) -> List[Backend]:
    return backends_factory([1, 2, 2], [False, False, False], [None, None, None], [None, None, None], [None, None, None])

@pytest.fixture
def backends_0_and_1_throttling(backends_factory) -> List[Backend]:
    return backends_factory([1, 1, 1], [True, True, False], [3, 1, None], [None, None, None], [None, None, None])

@pytest.fixture
def all_backends_throttling(backends_factory) -> List[Backend]:
    return backends_factory([1, 1, 1], [True, True, True], [3, 1, 5], [None, None, None], [None, None, None])

@pytest.fixture
def priority_backend_0_throttling(backends_factory) -> List[Backend]:
    return backends_factory([1, 2, 2], [True, False, False], [3, None, None], [None, None, None], [None, None, None])

@pytest.fixture(params=[backends_same_priority, backends_tiered_priority, backends_0_and_1_throttling, priority_backend_0_throttling])
def success_backends(request):
    return request.getfixturevalue(request.param.__name__)

@pytest.fixture(params=[all_backends_throttling])
def failure_backends(request):
    return request.getfixturevalue(request.param.__name__)

# Synchronous Client Fixtures

@pytest.fixture
def client_same_priority(backends_same_priority) -> AzureOpenAI:
    return create_client(backends_same_priority)

@pytest.fixture
def client_same_priority_custom_paths(backends_same_priority_custom_paths) -> AzureOpenAI:
    return create_client(backends_same_priority_custom_paths)

@pytest.fixture
def client_same_priority_api_keys(backends_same_priority_api_keys) -> AzureOpenAI:
    return create_client(backends_same_priority_api_keys)

@pytest.fixture
def client_successful_backends(success_backends) -> AzureOpenAI:
    return create_client(success_backends)

@pytest.fixture
def client_failure_backends(failure_backends) -> AzureOpenAI:
    return create_client(failure_backends)

# Asynchronous Client Fixtures

@pytest.fixture
def async_client_same_priority(backends_same_priority) -> AsyncAzureOpenAI:
    return create_async_client(backends_same_priority)

@pytest.fixture
def async_client_same_priority_custom_paths(backends_same_priority_custom_paths) -> AsyncAzureOpenAI:
    return create_async_client(backends_same_priority_custom_paths)

@pytest.fixture
def async_client_same_priority_api_keys(backends_same_priority_api_keys) -> AsyncAzureOpenAI:
    return create_async_client(backends_same_priority_api_keys)

@pytest.fixture
def async_client_successful_backends(success_backends) -> AsyncAzureOpenAI:
    return create_async_client(success_backends)

@pytest.fixture
def async_client_failure_backends(failure_backends) -> AsyncAzureOpenAI:
    return create_async_client(failure_backends)

##########################################################################################################################################################

# Tests

# Backend Tests

class TestBackend:
    @pytest.mark.backend
    def test_backend_instantiation(self) -> None:
        backend = Backend("oai-eastus.openai.azure.com", 1)

        assert backend.host == "oai-eastus.openai.azure.com"
        assert not backend.is_throttling
        assert backend.priority == 1
        assert backend.retry_after == datetime.min
        assert backend.successful_call_count == 0

# Synchronous Tests

class TestSynchronous:

    @pytest.mark.loadbalancer
    def test_loadbalancer_instantiation(self, backends_same_priority: List[Backend]) -> None:
        _lb = LoadBalancer(backends_same_priority)

        assert _lb.backends == backends_same_priority
        assert len(_lb.backends) == 3

        assert _lb.backends[0].host == "oai-eastus.openai.azure.com"
        assert not _lb.backends[0].is_throttling
        assert _lb.backends[0].priority == 1
        assert _lb.backends[0].retry_after == datetime.min
        assert _lb.backends[0].successful_call_count == 0

        assert _lb._backend_index == -1
        assert _lb._available_backends == 1
        assert isinstance(_lb._transport, httpx.Client)

    @pytest.mark.loadbalancer
    def test_loadbalancer_instantiation_with_backends_0_and_1_throttling(self, backends_0_and_1_throttling: List[Backend]) -> None:
        _lb = LoadBalancer(backends_0_and_1_throttling)

        assert _lb.backends == backends_0_and_1_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()

        selected_index = _lb._get_backend_index()
        assert selected_index == 2

        available_backends = _lb._get_available_backends()
        assert available_backends == 1

    @pytest.mark.loadbalancer
    def test_loadbalancer_instantiation_with_all_throttling(self, all_backends_throttling: List[Backend]) -> None:
        _lb = LoadBalancer(all_backends_throttling)

        assert _lb.backends == all_backends_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 0

        delay = _lb._get_soonest_retry_after()
        assert delay < 3    # 3 seconds is the second-fastest delay. Checking against the fastest delay, 1, has very occasional failed the test.

        response: httpx.Response = _lb._return_429()
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"

    @pytest.mark.skipif(SKIP_LONG_RUNNING_TESTS is True, reason = "Flag is set to skip long tests.")
    @pytest.mark.loadbalancer
    def test_loadbalancer_instantiation_with_all_throttling_then_resetting(self, all_backends_throttling: List[Backend]) -> None:
        _lb = LoadBalancer(all_backends_throttling)

        assert _lb.backends == all_backends_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 0
        selected_index = _lb._get_backend_index()
        assert selected_index == -1
        delay = _lb._get_soonest_retry_after()
        assert delay == 1

        time.sleep(6)

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 3

    @pytest.mark.loadbalancer
    def test_loadbalancer_different_priority(self, priority_backend_0_throttling: List[Backend]) -> None:
        _lb = LoadBalancer(priority_backend_0_throttling)
        selected_index = _lb._get_backend_index()

        assert selected_index != 0
        assert selected_index in (1, 2)

    @pytest.mark.loadbalancer
    def test_loadbalancer_handle_successful_requests(self, client_successful_backends):
        client = client_successful_backends

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.Client.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())
            response = client._client._transport.handle_request(req)

            assert response.status_code == 200

    @pytest.mark.loadbalancer
    def test_loadbalancer_modify_request_url_path(self, client_same_priority_custom_paths):
        client = client_same_priority_custom_paths

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.Client.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())

            assert req.url == 'https://foo.openai.azure.com/openai/completions?api-version=2024-04-01-preview'

            client._client._transport.handle_request(req)

            assert req.url in (
                'https://oai-eastus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview',
                'https://oai-westus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview',
                'https://oai-southcentralus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview'
            )

    @pytest.mark.loadbalancer
    def test_loadbalancer_use_api_keys(self, client_same_priority_api_keys):
        client = client_same_priority_api_keys

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.Client.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())

            assert req.url == 'https://foo.openai.azure.com/openai/completions?api-version=2024-04-01-preview'

            client._client._transport.handle_request(req)

            assert req.headers['api-key'] in (
                'c3d116584360f9960b38cccc5f44caba',
                '21c14252762502e8fc78b61e21db114f',
                'd6370785453b2b9c331a94cb1b7aaa36'
            )

    @pytest.mark.loadbalancer
    def test_loadbalancer_handle_failure_requests(self, client_failure_backends):
        client = client_failure_backends

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.Client.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())
            response = client._client._transport.handle_request(req)

            assert response.status_code == 429

    @pytest.mark.loadbalancer
    def test_loadbalancer_handle_429_failure(self, client_same_priority):
        client = client_same_priority

        # Create a sequence of mock responses for the transport
        mock_responses = [httpx.Response(429), httpx.Response(200)]

        with patch('httpx.Client.send', side_effect = mock_responses) as mock_send:
            req = client._build_request(create_final_request_options())
            response = client._client._transport.handle_request(req)

            # Assert that send was called twice: once for the initial request and once for the retry
            assert mock_send.call_count == 2

            # Assert that the final response status code was 200
            assert response.status_code == 200

    @pytest.mark.loadbalancer
    def test_loadbalancer_handle_all_backend_429_failure(self, client_same_priority):
        client = client_same_priority

        # Create a sequence of mock responses for the transport
        mock_responses = [httpx.Response(429), httpx.Response(429), httpx.Response(429)]

        with patch('httpx.Client.send', side_effect = mock_responses) as mock_send:
            req = client._build_request(create_final_request_options())
            response = client._client._transport.handle_request(req)

            # Assert that send was called twice: once for the initial request and once for the retry
            assert mock_send.call_count == 3

            # Assert that the final response status code was 200
            assert response.status_code == 429

    @pytest.mark.loadbalancer
    def test_loadbalancer_handle_4xx_failure(self, client_same_priority):
        client = client_same_priority

        # Create a mock response for the transport
        mock_response = httpx.Response(400)

        with patch('httpx.Client.send', return_value = mock_response) as mock_send:
            req = client._build_request(create_final_request_options())
            response = client._client._transport.handle_request(req)

            # Assert that send was called
            assert mock_send.call_count == 1

            # Assert that the final response status code was 400
            assert response.status_code == 400

# Asynchronous Tests

class TestAsynchronous:

    @pytest.mark.async_loadbalancer
    def test_async_loadbalancer_instantiation(self, backends_same_priority: List[Backend]) -> None:
        _lb = AsyncLoadBalancer(backends_same_priority)

        assert _lb.backends == backends_same_priority
        assert len(_lb.backends) == 3

        assert _lb.backends[0].host == "oai-eastus.openai.azure.com"
        assert not _lb.backends[0].is_throttling
        assert _lb.backends[0].priority == 1
        assert _lb.backends[0].retry_after == datetime.min
        assert _lb.backends[0].successful_call_count == 0

        assert _lb._backend_index == -1
        assert _lb._available_backends == 1
        assert isinstance(_lb._transport, httpx.AsyncClient)

    @pytest.mark.async_loadbalancer
    def test_async_loadbalancer_instantiation_with_backends_0_and_1_throttling(self, backends_0_and_1_throttling: List[Backend]) -> None:
        _lb = AsyncLoadBalancer(backends_0_and_1_throttling)

        assert _lb.backends == backends_0_and_1_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()

        selected_index = _lb._get_backend_index()
        assert selected_index == 2

        available_backends = _lb._get_available_backends()
        assert available_backends == 1


    @pytest.mark.async_loadbalancer
    def test_async_loadbalancer_instantiation_with_all_throttling(self, all_backends_throttling: List[Backend]) -> None:
        _lb = AsyncLoadBalancer(all_backends_throttling)

        assert _lb.backends == all_backends_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 0

        delay = _lb._get_soonest_retry_after()
        assert delay < 3    # 3 seconds is the second-fastest delay. Checking against the fastest delay, 1, has very occasional failed the test.

        response: httpx.Response = _lb._return_429()
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"

    @pytest.mark.skipif(SKIP_LONG_RUNNING_TESTS is True, reason = "Flag is set to skip long tests.")
    @pytest.mark.async_loadbalancer
    def test_async_loadbalancer_instantiation_with_all_throttling_then_resetting(self, all_backends_throttling: List[Backend]) -> None:
        _lb = AsyncLoadBalancer(all_backends_throttling)

        assert _lb.backends == all_backends_throttling
        assert len(_lb.backends) == 3

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 0
        selected_index = _lb._get_backend_index()
        assert selected_index == -1
        delay = _lb._get_soonest_retry_after()
        assert delay == 1

        time.sleep(6)

        _lb._check_throttling()
        available_backends = _lb._get_available_backends()
        assert available_backends == 3

    @pytest.mark.async_loadbalancer
    def test_async_loadbalancer_different_priority(self, priority_backend_0_throttling: List[Backend]) -> None:
        _lb = AsyncLoadBalancer(priority_backend_0_throttling)
        selected_index = _lb._get_backend_index()

        assert selected_index != 0
        assert selected_index in (1, 2)

    @pytest.mark.asyncio
    @pytest.mark.async_loadbalancer
    async def test_async_loadbalancer_handle_successful_requests(self, async_client_successful_backends):
        client = async_client_successful_backends

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.AsyncClient.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())
            response = await client._client._transport.handle_async_request(req)

            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.loadbalancer
    async def test_async_loadbalancer_modify_request_url_path(self, async_client_same_priority_custom_paths):
        client = async_client_same_priority_custom_paths

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.AsyncClient.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())

            assert req.url == 'https://foo.openai.azure.com/openai/completions?api-version=2024-04-01-preview'

            await client._client._transport.handle_async_request(req)

            assert req.url in (
                'https://oai-eastus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview',
                'https://oai-westus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview',
                'https://oai-southcentralus.openai.azure.com/ai/openai/completions?api-version=2024-04-01-preview'
            )

    @pytest.mark.asyncio
    @pytest.mark.loadbalancer
    async def test_async_loadbalancer_use_api_keys(self, async_client_same_priority_api_keys):
        client = async_client_same_priority_api_keys

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.AsyncClient.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())

            assert req.url == 'https://foo.openai.azure.com/openai/completions?api-version=2024-04-01-preview'

            await client._client._transport.handle_async_request(req)

            assert req.headers['api-key'] in (
                'c3d116584360f9960b38cccc5f44caba',
                '21c14252762502e8fc78b61e21db114f',
                'd6370785453b2b9c331a94cb1b7aaa36'
            )

    @pytest.mark.asyncio
    @pytest.mark.async_loadbalancer
    async def test_async_loadbalancer_handle_failure_requests(self, async_client_failure_backends):
        client = async_client_failure_backends

        # Create a mock response for the transport
        mock_response = httpx.Response(200)

        with patch('httpx.AsyncClient.send', return_value = mock_response):
            req = client._build_request(create_final_request_options())

            response = await client._client._transport.handle_async_request(req)

            assert response.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.async_loadbalancer
    async def test_async_loadbalancer_handle_429_failure(self, async_client_same_priority):
        client = async_client_same_priority

        # Create a sequence of mock responses for the transport
        mock_responses = [httpx.Response(429), httpx.Response(200)]

        with patch('httpx.AsyncClient.send', side_effect = mock_responses) as mock_send:
            req = client._build_request(create_final_request_options())
            response = await client._client._transport.handle_async_request(req)

            # Assert that send was called twice: once for the initial request and once for the retry
            assert mock_send.call_count == 2

            # Assert that the final response status code was 200
            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.async_loadbalancer
    async def test_async_loadbalancer_handle_all_backend_429_failure(self, async_client_same_priority):
        client = async_client_same_priority

        # Create a sequence of mock responses for the transport
        mock_responses = [httpx.Response(429), httpx.Response(429), httpx.Response(429)]

        with patch('httpx.AsyncClient.send', side_effect = mock_responses) as mock_send:
            req = client._build_request(create_final_request_options())
            response = await client._client._transport.handle_async_request(req)

            # Assert that send was called twice: once for the initial request and once for the retry
            assert mock_send.call_count == 3

            # Assert that the final response status code was 200
            assert response.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.async_loadbalancer
    async def test_async_loadbalancer_handle_4xx_failure(self, async_client_same_priority):
        client = async_client_same_priority

        # Create a mock response for the transport
        mock_response = httpx.Response(400)

        with patch('httpx.AsyncClient.send', return_value = mock_response) as mock_send:
            req = client._build_request(create_final_request_options())
            response = await client._client._transport.handle_async_request(req)

            # Assert that send was called
            assert mock_send.call_count == 1

            # Assert that the final response status code was 400
            assert response.status_code == 400
