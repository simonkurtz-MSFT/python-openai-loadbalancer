"""Module providing an OpenAI Priority Load Balancer test harness."""

import asyncio
import logging
import time
import traceback
from typing import List
from datetime import datetime
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, AsyncAzureOpenAI, DefaultAsyncHttpxClient, DefaultHttpxClient, NotFoundError
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import AsyncLoadBalancer, LoadBalancer, Backend


##########################################################################################################################################################

# >>> Only make changes to TEST_EXECUTIONS, NUM_OF_REQUESTS, MODEL, AZURE_ENDPOINT, and the backends list <<<

class TestExecutions:
    """Class representing the tests that can be performed."""

    def __init__(self):
        self.standard                   = True
        self.load_balanced              = True
        self.async_load_balanced        = True
        self.stream_load_balanced       = True
        self.async_stream_load_balanced = True

LOG_LEVEL                               = logging.INFO
NUM_OF_REQUESTS                         = 5
MODEL                                   = "<your-aoai-model>"  # the model, also known as the Deployment in Azure OpenAI, is common across standard and load-balanced requests
AZURE_ENDPOINT                          = "https://oai-eastus-xxxxxxxx.openai.azure.com"
backends: List[Backend] = [
    Backend("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-southcentralus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-westus-xxxxxxxx.openai.azure.com", 1)
]

##########################################################################################################################################################

# get_bearer_token_provider automatically caches and refreshes tokens.
# https://github.com/openai/openai-python/blob/main/examples/azure_ad.py#L5
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# Standard Azure OpenAI Implementation (One Backend)
def send_request(num_of_requests, azure_endpoint: str):
    """Function to send standard requests to the Azure OpenAI API."""

    try:
        client = AzureOpenAI(
            azure_endpoint = azure_endpoint,
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview"
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Standard request {i+1}/{num_of_requests}")

            response = client.chat.completions.create(
                model = MODEL,
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                ]
            )

            print(f"{datetime.now()}:\n{response}\n\n\n")

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Load-balanced Azure OpenAI Implementation (Multiple Backends)
def send_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced requests to the Azure OpenAI API."""

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = LoadBalancer(backends)

        client = AzureOpenAI(
            azure_endpoint = f"https://{backends[0].host}",         # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview",
            http_client = DefaultHttpxClient(transport = lb)        # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = client.chat.completions.create(
                    model = MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                print(f"{datetime.now()}:\n{response}\n\n\n")
            except Exception:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

async def send_async_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced requests to the Azure OpenAI API."""

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = AsyncLoadBalancer(backends)

        client = AsyncAzureOpenAI(
            azure_endpoint = f"https://{backends[0].host}",         # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview",
            http_client = DefaultAsyncHttpxClient(transport = lb)   # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = await client.chat.completions.create(
                    model = MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                print(f"{datetime.now()}:\n{response}\n\n\n")
            except Exception:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Reference design: https://cookbook.openai.com/examples/how_to_stream_completions
def send_stream_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced streaming requests to the Azure OpenAI API."""

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = LoadBalancer(backends)

        client = AzureOpenAI(
            azure_endpoint = f"https://{backends[0].host}",         # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview",
            http_client = DefaultHttpxClient(transport = lb)        # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                stream_start_time = time.time()

                response = client.chat.completions.create(
                    model = MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {'role': 'user', 'content': 'Count to 5, with a comma between each number and no newlines. E.g., 1, 2, 3, ...'}
                    ],
                    stream = True,
                )

                # Create variables to collect the stream of chunks
                collected_chunks = []
                collected_messages = []

                # Iterate through the stream of events
                for chunk in response:  # pylint: disable=E1133
                    chunk_time = time.time() - stream_start_time  # calculate the time delay of the chunk
                    collected_chunks.append(chunk)  # save the event response

                    if chunk.choices and chunk.choices[0] and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        chunk_message = chunk.choices[0].delta.content  # extract the message
                        collected_messages.append(chunk_message)  # save the message
                        print(f"Message received {chunk_time:.2f} seconds after request: {chunk_message}")  # print the delay and text

                # Print the time delay and text received
                print(f"\nFull response received {chunk_time:.2f} seconds after request.")
                collected_messages = [m for m in collected_messages if m is not None]   # Clean None in collected_messages
                full_reply_content = ''.join(collected_messages)
                print(f"\nFull conversation received: {full_reply_content}\n\n")

            except Exception:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Reference design: https://cookbook.openai.com/examples/how_to_stream_completions
async def send_async_stream_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced streaming requests to the Azure OpenAI API."""

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = AsyncLoadBalancer(backends)

        client = AsyncAzureOpenAI(
            azure_endpoint = f"https://{backends[0].host}",         # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview",
            http_client = DefaultAsyncHttpxClient(transport = lb)   # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                stream_start_time = time.time()

                response = await client.chat.completions.create(
                    model = MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {'role': 'user', 'content': 'Count to 5, with a comma between each number and no newlines. E.g., 1, 2, 3, ...'}
                    ],
                    stream = True,
                )

                # Create variables to collect the stream of chunks
                collected_chunks = []
                collected_messages = []

                if response is not None:
                    # Iterate through the stream of events
                    async for chunk in response:
                        chunk_time = time.time() - stream_start_time  # calculate the time delay of the chunk
                        collected_chunks.append(chunk)  # save the event response

                        if chunk.choices and chunk.choices[0] and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            chunk_message = chunk.choices[0].delta.content  # extract the message
                            collected_messages.append(chunk_message)  # save the message
                            print(f"Message received {chunk_time:.2f} seconds after request: {chunk_message}")  # print the delay and text

                    # Print the time delay and text received
                    print(f"\nFull response received {chunk_time:.2f} seconds after request.")
                    collected_messages = [m for m in collected_messages if m is not None]   # Clean None in collected_messages
                    full_reply_content = ''.join(collected_messages)
                    print(f"\nFull conversation received: {full_reply_content}\n\n")

            except Exception:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

##########################################################################################################################################################

# >>> TEST HARNESS <<<

# Set up the logger: https://www.machinelearningplus.com/python/python-logging-guide/
logging.basicConfig(
    format = '%(asctime)s %(levelname)-8s %(module)-30s %(message)s',
    level = LOG_LEVEL,
    datefmt = '%Y-%m-%d %H:%M:%S'
)

# Ensure that variables are set.
if MODEL == "<your-aoai-model>":
    raise ValueError("MODEL must be set to a valid AOAI model.")

if "xxxxxxxx" in AZURE_ENDPOINT:
    raise ValueError("AZURE_ENDPOINT must be set to a valid endpoint.")

for backend in backends:
    if "xxxxxxxx" in backend.host:
        raise ValueError(f"Backend {backend.host} must be set to a valid endpoint.")

# Instantiate the TestExecutions object to understand which tests to run.
test_executions = TestExecutions()

# 1: Standard requests to one AOAI backend
if test_executions.standard:
    print(f"\nStandard Requests\n{'-' * 17}\n")
    start_time = time.time()
    send_request(NUM_OF_REQUESTS, AZURE_ENDPOINT)
    end_time = time.time()

# 2: Load-balanced requests to one or more AOAI backends
if test_executions.load_balanced:
    print(f"\nLoad Balanced Requests\n{'-' * 22}\n")
    lb_start_time = time.time()
    send_loadbalancer_request(NUM_OF_REQUESTS)
    lb_end_time = time.time()

# 3: Async Load-balanced requests to one or more AOAI backends
if test_executions.async_load_balanced:
    print(f"\nAsync Load Balanced Requests\n{'-' * 28}\n")
    async_lb_start_time = time.time()
    asyncio.run(send_async_loadbalancer_request(NUM_OF_REQUESTS))
    async_lb_end_time = time.time()

# 4: Load-balanced streaming requests to one or more AOAI backends
if test_executions.stream_load_balanced:
    print(f"\nStream Load Balanced Requests\n{'-' * 29}\n")
    stream_lb_start_time = time.time()
    send_stream_loadbalancer_request(NUM_OF_REQUESTS)
    stream_lb_end_time = time.time()

# 5: Async Load-balanced streaming requests to one or more AOAI backends
if test_executions.async_stream_load_balanced:
    print(f"\nStream Async Load Balanced Requests\n{'-' * 35}\n")
    async_stream_lb_start_time = time.time()
    asyncio.run(send_async_stream_loadbalancer_request(NUM_OF_REQUESTS))
    async_stream_lb_end_time = time.time()

# Statistics
print(f"\n{'*' * 100}\n")
print(f"Number of requests                              : {NUM_OF_REQUESTS}\n")

if test_executions.standard:
    print(f"Single instance operation duration              : {end_time - start_time:.2f} seconds")
if test_executions.load_balanced:
    print(f"Load-balancer operation duration                : {lb_end_time - lb_start_time:.2f} seconds")
if test_executions.async_load_balanced:
    print(f"Async Load-balancer operation duration          : {async_lb_end_time - async_lb_start_time:.2f} seconds")
if test_executions.stream_load_balanced:
    print(f"Stream Load-balancer operation duration         : {stream_lb_end_time - stream_lb_start_time:.2f} seconds")
if test_executions.async_stream_load_balanced:
    print(f"Stream Async Load-balancer operation duration   : {async_stream_lb_end_time - async_stream_lb_start_time:.2f} seconds")

print("\n\n")
