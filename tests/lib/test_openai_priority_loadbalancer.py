# pylint: disable=C0114,C0115,C0116,W0212,W0621

# Execute with "pytest -v" in the root directory

# https://docs.pytest.org/en/8.2.x/
# Reference test file for AzureOpenAI: https://github.com/kristapratico/openai-python/blob/main/tests/lib/test_azure.py

import os
import sys
from datetime import datetime
from typing import List

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import Backend, LoadBalancer  # pylint: disable=C0413

@pytest.fixture
def backends() -> List[Backend]:
    return [
        Backend("oai-eastus.openai.azure.com", 1),
        Backend("oai-southcentralus.openai.azure.com", 1),
        Backend("oai-west.openai.azure.com", 1),
    ]

@pytest.fixture
def lb(backends: List[Backend]) -> LoadBalancer:
    return LoadBalancer(backends)

@pytest.mark.backend
def test_backend_instantiation() -> None:
    backend = Backend("oai-eastus.openai.azure.com", 1)

    assert backend.host == "oai-eastus.openai.azure.com"
    assert not backend.is_throttling
    assert backend.priority == 1
    assert backend.retry_after == datetime.min
    assert backend.successful_call_count == 0


@pytest.mark.loadbalancer
def test_loadbalancer_instantiation(backends: List[Backend]) -> None:
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
