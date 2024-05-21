# pylint: disable=C0114,C0115,C0116,W0212,W0621

# Execute with "pytest -v" in the root directory

# https://docs.pytest.org/en/8.2.x/
# Reference test file for AzureOpenAI: https://github.com/kristapratico/openai-python/blob/main/tests/lib/test_azure.py

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Union

from unittest.mock import patch, Mock
import time
import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import AsyncLoadBalancer, Backend, BaseLoadBalancer, LoadBalancer  # pylint: disable=C0413

from openai._models import FinalRequestOptions
from openai.lib.azure import AzureOpenAI, AsyncAzureOpenAI, BaseAzureClient

##########################################################################################################################################################


#_HttpxClientT = TypeVar("_HttpxClientT", bound=Union[httpx.Client, httpx.AsyncClient])


# Utility Functions

def in_seconds(secs: int) -> int:
    return datetime.now(timezone.utc) + timedelta(seconds = secs)

# Private variables

_backends_same_priority: List[Backend] = [
    Backend("oai-eastus.openai.azure.com", 1),
    Backend("oai-southcentralus.openai.azure.com", 1),
    Backend("oai-west.openai.azure.com", 1),
]

_backends_tiered_priority: List[Backend] = [
    Backend("oai-eastus.openai.azure.com", 1),
    Backend("oai-southcentralus.openai.azure.com", 2),
    Backend("oai-west.openai.azure.com", 2),
]

# Test Fixtures

@pytest.fixture
def backends_same_priority() -> List[Backend]:
    return _backends_same_priority

@pytest.fixture
def backends_tiered_priority() -> List[Backend]:
    return _backends_tiered_priority

# @pytest.fixture(params=[backends_same_priority, backends_tiered_priority])
# def backends(request):
#     return request.getfixturevalue(request.param.__name__)

@pytest.fixture
def backends_0_and_1_throttling(backends_same_priority: List[Backend]) -> List[Backend]:
    backends = backends_same_priority

    backends[0].is_throttling = True
    backends[0].retry_after = in_seconds(3)

    backends[1].is_throttling = True
    backends[1].retry_after = in_seconds(1)

    return backends

@pytest.fixture
def all_backends_throttling(backends_0_and_1_throttling: List[Backend]) -> List[Backend]:
    backends = backends_0_and_1_throttling

    backends[2].is_throttling = True
    backends[2].retry_after = in_seconds(5)

    return backends

@pytest.fixture
def priority_backend_0_throttling(backends_tiered_priority: List[Backend]) -> List[Backend]:
    backends = backends_tiered_priority

    backends[0].is_throttling = True
    backends[0].retry_after = in_seconds(3)

    return backends

Client: BaseAzureClient = Union[AzureOpenAI, AsyncAzureOpenAI]
#Client = Union[AzureOpenAI, AsyncAzureOpenAI]
Transport: BaseLoadBalancer = Union[LoadBalancer, AsyncLoadBalancer]

class MockTransport:
    def send(self, *args, **kwargs):
        return httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"})



lb = LoadBalancer(_backends_same_priority)

sync_client =  AzureOpenAI(
    azure_endpoint = "https://foo.openai.azure.com",        # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
    api_key="example API key",
    api_version = "2024-04-01-preview",
    http_client = httpx.Client(transport = lb)              # Inject the load balancer as the transport in a new default httpx client
)

async_lb = AsyncLoadBalancer(_backends_same_priority)

async_client =  AsyncAzureOpenAI(
    azure_endpoint = "https://foo.openai.azure.com",        # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
    api_key="example API key",
    api_version = "2024-04-01-preview",
    http_client = httpx.AsyncClient(transport = async_lb)   # Inject the load balancer as the transport in a new default httpx client
)


def create_client(backends: List[Backend]) -> AzureOpenAI:
    lb = LoadBalancer(backends)

    return AzureOpenAI(
        azure_endpoint = "https://foo.openai.azure.com",
        api_key = "example API key",
        api_version = "2024-04-01-preview",
        http_client = httpx.Client(transport = lb)
    )


@pytest.fixture(params=[backends_same_priority, backends_tiered_priority, backends_0_and_1_throttling, priority_backend_0_throttling])
def success_backends(request):
    return request.getfixturevalue(request.param.__name__)

@pytest.fixture
def client_successful_backends(success_backends):
    return create_client(success_backends)

@pytest.fixture(params=[all_backends_throttling])
def failure_backends(request):
    return request.getfixturevalue(request.param.__name__)

@pytest.fixture
def client_failure_backends(failure_backends):
    return create_client(failure_backends)

##########################################################################################################################################################

# Tests

#https://stackoverflow.com/questions/70633584/how-to-mock-httpx-asyncclient-in-pytest

@pytest.mark.loadbalancer
def test_handle_successful_requests(client_successful_backends):
    client = client_successful_backends

    # Create a mock response for the transport
    mock_response = httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"})

    with patch('httpx.Client.send', return_value = mock_response):
        req = client._build_request(
            FinalRequestOptions.construct(
                method="post",
                url="/chat/completions",
                json_data={"model": "my-deployment-model"},
            )
        )

        response = client._client._transport.handle_request(req)

        assert response.status_code == 200

@pytest.mark.loadbalancer
def test_handle_failured_requests(client_failure_backends):
    client = client_failure_backends

    # Create a mock response for the transport
    mock_response = httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"})

    with patch('httpx.Client.send', return_value = mock_response):
        req = client._build_request(
            FinalRequestOptions.construct(
                method="post",
                url="/chat/completions",
                json_data={"model": "my-deployment-model"},
            )
        )

        response = client._client._transport.handle_request(req)

        assert response.status_code == 429



@pytest.mark.skip()
@pytest.mark.loadbalancer
@pytest.mark.parametrize("client", [(sync_client)])
def test_handle_request_200(client) -> None:
    # Create a mock response for the transport
    mock_response = httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"})

    with patch('httpx.Client.send', return_value = mock_response):
        load_balancer = LoadBalancer(_backends_same_priority)

        req = client._build_request(
            FinalRequestOptions.construct(
                method = "post",
                url = "/chat/completions",
                json_data = {"model": "my-deployment-model"},
            )
        )

        response = load_balancer.handle_request(req)

        assert response.status_code == 200


















@pytest.mark.skip()
@pytest.mark.backend
def test_backend_instantiation() -> None:
    backend = Backend("oai-eastus.openai.azure.com", 1)

    assert backend.host == "oai-eastus.openai.azure.com"
    assert not backend.is_throttling
    assert backend.priority == 1
    assert backend.retry_after == datetime.min
    assert backend.successful_call_count == 0

@pytest.mark.skip()
@pytest.mark.loadbalancer
def test_loadbalancer_instantiation(backends_same_priority: List[Backend]) -> None:
    backends = backends_same_priority

    _lb = LoadBalancer(backends)

    assert _lb.backends == backends
    assert len(_lb.backends) == 3

    assert _lb.backends[0].host == "oai-eastus.openai.azure.com"
    assert not _lb.backends[0].is_throttling
    assert _lb.backends[0].priority == 1
    assert _lb.backends[0].retry_after == datetime.min
    assert _lb.backends[0].successful_call_count == 0

    assert _lb._backend_index == -1
    assert _lb._available_backends == 1
    assert isinstance(_lb._transport, httpx.Client)

@pytest.mark.skip()
@pytest.mark.loadbalancer
def test_loadbalancer_instantiation_with_backends_0_and_1_throttling(backends_0_and_1_throttling: List[Backend]) -> None:
    _lb = LoadBalancer(backends_0_and_1_throttling)
    assert _lb.backends == backends_0_and_1_throttling
    assert len(_lb.backends) == 3

    _lb._check_throttling()

    selected_index = _lb._get_backend_index()
    assert selected_index == 2

    available_backends = _lb._get_available_backends()
    assert available_backends == 1

@pytest.mark.skip()
@pytest.mark.loadbalancer
def test_loadbalancer_instantiation_with_all_throttling(all_backends_throttling: List[Backend]) -> None:
    _lb = LoadBalancer(all_backends_throttling)
    assert _lb.backends == all_backends_throttling
    assert len(_lb.backends) == 3

    _lb._check_throttling()
    available_backends = _lb._get_available_backends()
    assert available_backends == 0

    delay = _lb._get_soonest_retry_after()
    assert delay == 1

    response: httpx.Response = _lb._return_429()
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"

@pytest.mark.skip(reason="This test is sleeping too long to always execute.")
@pytest.mark.loadbalancer
def test_loadbalancer_instantiation_with_all_throttling_then_resetting(all_backends_throttling: List[Backend]) -> None:
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

@pytest.mark.skip()
@pytest.mark.loadbalancer
def test_loadbalancer_different_priority(priority_backend_0_throttling: List[Backend]) -> None:
    _lb = LoadBalancer(priority_backend_0_throttling)
    selected_index = _lb._get_backend_index()

    assert selected_index != 0
    assert selected_index in (1, 2)






@pytest.mark.skip()
@pytest.mark.asyncio
#@patch.object(LoadBalancer, "handle_request", return_value= httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"}))
#@patch.object(BaseLoadBalancer._transport, "send", return_value= httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"}))
#@patch.object(AsyncLoadBalancer, "handle_async_request", return_value= httpx.Response(200, json={"id": "9ed7dasdasd-08ff-4ae1-8952-37e3a323eb08"}))
#@pytest.mark.parametrize("client, client_type, transport", [(sync_client, httpx.Client, LoadBalancer), (async_client, httpx.AsyncClient, AsyncLoadBalancer)])
@pytest.mark.parametrize("client, client_type, transport", [(sync_client, httpx.Client, LoadBalancer)])
# async def test_client_instantiation(mock_handle_request: Mock, mock_handle_async_request: Mock, client, client_type, transport) -> None:
#async def test_client_instantiation(mock_handle_request: Mock, client, client_type, transport) -> None:
#async def test_client_instantiation(mock_send: Mock, client, client_type, transport) -> None:
async def test_client_instantiation(client, client_type, transport) -> None:
    mock_transport = MockTransport()
    with patch.object(BaseLoadBalancer, '_transport', new = mock_transport):
        assert isinstance(client._client, client_type)
        assert isinstance(client._client._transport, transport)
        assert client._client._transport.backends is not None
        assert len(client._client._transport.backends) == 3

        req = client._build_request(
            FinalRequestOptions.construct(
                method="POST",
                url="/chat/completions",
                json_data={"model": "my-deployment-model"},
            )
        )

        response: httpx.Response = None

        assert isinstance(client._client, httpx.Client)

        if isinstance(client._client, httpx.Client):
            response = client._client._transport.handle_request(req)
            #mock_transport.send.assert_called_once()
        # elif isinstance(client._client, httpx.AsyncClient):
        #     response = await client._client._transport.handle_async_request(req)
        #     mock_handle_async_request.assert_called_once()


        assert response.status_code == 200
