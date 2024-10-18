# pylint: disable=C0115

"""Module providing configuration settings for the OpenAI Priority Load Balancer test harness."""

from typing import List
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import Backend

NUM_OF_REQUESTS = 5
MODEL           = "<your-aoai-model>"  # the model, also known as the Deployment in Azure OpenAI, is common across standard and load-balanced requests
AZURE_ENDPOINT  = "https://oai-eastus-xxxxxxxx.openai.azure.com"
API_VERSION     = "2024-08-01-preview"

backends: List[Backend] = [
    Backend("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-southcentralus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-westus-xxxxxxxx.openai.azure.com", 1)
]

backends_with_api_keys: List[Backend] = [
    Backend("oai-eastus-xxxxxxxx.openai.azure.com", 1, None, 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'),
    Backend("oai-southcentralus-xxxxxxxx.openai.azure.com", 1, None, 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'),
    Backend("oai-westus-xxxxxxxx.openai.azure.com", 1, None, 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
]
