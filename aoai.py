"""Module providing an OpenAI Priority Load Balancer test harness."""

import asyncio
import logging
import time
import traceback
from datetime import datetime
# Using httpx.Client and httpx.AsyncClient avoids having to update openai to 1.17.1 or newer.
# The openai properties for DefaultHttpxClient and DefaultAsyncHttpxClient are mere wrappers for httpx.Client and httpx.AsyncClient.
# https://github.com/openai/openai-python/releases/tag/v1.17.0
import httpx
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI, AsyncAzureOpenAI, NotFoundError, APIError
from src.openai_priority_loadbalancer.openai_priority_loadbalancer import AsyncLoadBalancer, LoadBalancer
import config

##########################################################################################################################################################

# >>> Only make changes to TEST_EXECUTIONS, NUM_OF_REQUESTS, MODEL, AZURE_ENDPOINT, and the backends list <<<

class TestExecutions:
    """Class representing the tests that can be performed."""

    def __init__(self):
        self.standard                           = True
        self.load_balanced                      = True
        self.load_balanced_with_api_keys        = True
        self.async_load_balanced                = True
        self.async_load_balanced_with_api_keys  = True
        self.stream_load_balanced               = True
        self.async_stream_load_balanced         = True

LOG_LEVEL = logging.INFO     # change to DEBUG for detailed information

##########################################################################################################################################################

# get_bearer_token_provider automatically caches and refreshes tokens.
# https://github.com/openai/openai-python/blob/main/examples/azure_ad.py#L5
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# Standard Azure OpenAI Implementation (One Backend)
def send_request(num_of_requests: int, azure_endpoint: str):
    """Function to send standard requests to the Azure OpenAI API."""

    global counter, success_counter

    try:
        client = AzureOpenAI(
            azure_endpoint = azure_endpoint,
            azure_ad_token_provider = token_provider,
            api_version = config.API_VERSION
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Standard request {i+1}/{num_of_requests}")

            response = client.chat.completions.create(
                model = config.MODEL,
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                ]
            )

            success_counter += 1
            counter += 1
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

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = LoadBalancer(config.backends)

        client = AzureOpenAI(
            azure_endpoint = f"https://{config.backends[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = config.API_VERSION,
            http_client = httpx.Client(transport = lb)      # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = client.chat.completions.create(
                    model = config.MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                success_counter += 1
                print(f"{datetime.now()}:\n{response}\n\n\n")
            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()
                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Load-balanced Azure OpenAI Implementation (Multiple Backends)
def send_loadbalancer_request_with_api_keys(num_of_requests: int):
    """Function to send load-balanced requests to the Azure OpenAI API using API keys."""

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = LoadBalancer(config.backends_with_api_keys)

        client = AzureOpenAI(
            azure_endpoint = f"https://{config.backends_with_api_keys[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            api_key = "obtain_from_load_balancer",          # the value is not used, but it must be set
            api_version = config.API_VERSION,
            http_client = httpx.Client(transport = lb)      # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = client.chat.completions.create(
                    model = config.MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                success_counter += 1
                print(f"{datetime.now()}:\n{response}\n\n\n")
            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()
                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

async def send_async_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced requests to the Azure OpenAI API."""

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = AsyncLoadBalancer(config.backends)

        client = AsyncAzureOpenAI(
            azure_endpoint = f"https://{config.backends[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = config.API_VERSION,
            http_client = httpx.AsyncClient(transport = lb) # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = await client.chat.completions.create(
                    model = config.MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                success_counter += 1
                print(f"{datetime.now()}:\n{response}\n\n\n")
            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()
                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

async def send_async_loadbalancer_request_with_api_keys(num_of_requests: int):
    """Function to send load-balanced requests to the Azure OpenAI API using API keys."""

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = AsyncLoadBalancer(config.backends_with_api_keys)

        client = AsyncAzureOpenAI(
            azure_endpoint = f"https://{config.backends_with_api_keys[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            api_key = "obtain_from_load_balancer",          # the value is not used, but it must be set
            api_version = config.API_VERSION,
            http_client = httpx.AsyncClient(transport = lb) # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                response = await client.chat.completions.create(
                    model = config.MODEL,
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                    ]
                )

                success_counter += 1
                print(f"{datetime.now()}:\n{response}\n\n\n")
            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()
                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Reference design: https://cookbook.openai.com/examples/how_to_stream_completions
def send_stream_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced streaming requests to the Azure OpenAI API."""

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = LoadBalancer(config.backends)

        client = AzureOpenAI(
            azure_endpoint = f"https://{config.backends[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = config.API_VERSION,
            http_client = httpx.Client(transport = lb)      # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                stream_start_time = time.time()

                response = client.chat.completions.create(
                    model = config.MODEL,
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
                success_counter += 1

            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()
                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

# Reference design: https://cookbook.openai.com/examples/how_to_stream_completions
async def send_async_stream_loadbalancer_request(num_of_requests: int):
    """Function to send load-balanced streaming requests to the Azure OpenAI API."""

    global counter, failure_counter, success_counter

    try:
        # Instantiate the LoadBalancer class and create a new https client with the load balancer as the injected transport.
        lb = AsyncLoadBalancer(config.backends)

        client = AsyncAzureOpenAI(
            azure_endpoint = f"https://{config.backends[0].host}", # Must be seeded, so we use the first host. It will get overwritten by the load balancer.
            azure_ad_token_provider = token_provider,
            api_version = config.API_VERSION,
            http_client = httpx.AsyncClient(transport = lb) # Inject the load balancer as the transport in a new default httpx client
        )

        for i in range(num_of_requests):
            print(f"{datetime.now()}: Async LoadBalancer request {i+1}/{num_of_requests}")

            try:
                stream_start_time = time.time()

                response = await client.chat.completions.create(
                    model = config.MODEL,
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
                    success_counter += 1

            except APIError as e:
                if e.code == 429:
                    print(f"{datetime.now()}: Rate limit exceeded. Python OpenAI Library has exhausted all of its retries.")
                else:
                    print(f"{datetime.now()}: Python OpenAI Library request failure.")

                failure_counter += 1
            except Exception:
                traceback.print_exc()

                failure_counter += 1

            counter += 1

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

##########################################################################################################################################################

# >>> TEST HARNESS <<<

success_counter = failure_counter = counter = 0 # pylint: disable=C0103

# Set up the logger: https://www.machinelearningplus.com/python/python-logging-guide/
logging.basicConfig(
    format = '%(asctime)s %(levelname)-8s %(module)-30s %(message)s',
    level = LOG_LEVEL,
    datefmt = '%Y-%m-%d %H:%M:%S'
)

# Ensure that variables are set.
if config.MODEL == "<your-aoai-model>":
    raise ValueError("MODEL must be set to a valid AOAI model.\n")

if "xxxxxxxx" in config.AZURE_ENDPOINT:
    raise ValueError("AZURE_ENDPOINT must be set to a valid endpoint.\n")

for backend in config.backends:
    if "xxxxxxxx" in backend.host:
        raise ValueError(f"Backend {backend.host} must be set to a valid endpoint.\n")

# Instantiate the TestExecutions object to understand which tests to run.
test_executions = TestExecutions()

# 1: Standard requests to one AOAI backend
if test_executions.standard:
    print(f"\nStandard Requests\n{'-' * 17}\n")
    start_time = time.time()
    send_request(config.NUM_OF_REQUESTS, config.AZURE_ENDPOINT)
    end_time = time.time()

# 2: Load-balanced requests to one or more AOAI backends
if test_executions.load_balanced:
    print(f"\nLoad Balanced Requests\n{'-' * 22}\n")
    lb_start_time = time.time()
    send_loadbalancer_request(config.NUM_OF_REQUESTS)
    lb_end_time = time.time()

# 3: Load-balanced requests to one or more AOAI backends with API keys
if test_executions.load_balanced_with_api_keys:
    print(f"\nLoad Balanced Requests With API Keys\n{'-' * 36}\n")
    lb_with_api_keys_start_time = time.time()
    send_loadbalancer_request_with_api_keys(config.NUM_OF_REQUESTS)
    lb_with_api_keys_end_time = time.time()

# 4: Async Load-balanced requests to one or more AOAI backends
if test_executions.async_load_balanced:
    print(f"\nAsync Load Balanced Requests\n{'-' * 28}\n")
    async_lb_start_time = time.time()
    asyncio.run(send_async_loadbalancer_request(config.NUM_OF_REQUESTS))
    async_lb_end_time = time.time()

# 5: Async Load-balanced requests to one or more AOAI backends with API keys
if test_executions.async_load_balanced_with_api_keys:
    print(f"\nAsync Load Balanced Requests With API Keys\n{'-' * 42}\n")
    async_lb_with_api_keys_start_time = time.time()
    asyncio.run(send_async_loadbalancer_request_with_api_keys(config.NUM_OF_REQUESTS))
    async_lb_with_api_keys_end_time = time.time()

# : Load-balanced streaming requests to one or more AOAI backends
if test_executions.stream_load_balanced:
    print(f"\nStream Load Balanced Requests\n{'-' * 29}\n")
    stream_lb_start_time = time.time()
    send_stream_loadbalancer_request(config.NUM_OF_REQUESTS)
    stream_lb_end_time = time.time()

# 5: Async Load-balanced streaming requests to one or more AOAI backends
if test_executions.async_stream_load_balanced:
    print(f"\nStream Async Load Balanced Requests\n{'-' * 35}\n")
    async_stream_lb_start_time = time.time()
    asyncio.run(send_async_stream_loadbalancer_request(config.NUM_OF_REQUESTS))
    async_stream_lb_end_time = time.time()

# Statistics
WIDTH = 16
SECONDS_WIDTH = WIDTH - 8

print(f"\n{'*' * 100}\n")
print(f"Requests per approach                                   : {str(config.NUM_OF_REQUESTS).rjust(WIDTH)}")
print(f"Number of approaches                                    : {str(sum(1 for value in vars(test_executions).values() if value is True)).rjust(WIDTH)}\n")

print(f"Total requests                                          : {str(counter).rjust(WIDTH)}")
print(f"Total successful requests                               : {str(success_counter).rjust(WIDTH)}")
print(f"Total failed requests                                   : {str(failure_counter).rjust(WIDTH)}")
print(f"Total successful requests percentage                    : {('{:.2%}'.format(success_counter / counter)).rjust(WIDTH)}")     # pylint: disable=C0209
print(f"Total Failed requests percentage                        : {('{:.2%}'.format(failure_counter / counter)).rjust(WIDTH)}\n")   # pylint: disable=C0209

if test_executions.standard:
    print(f"Single instance operation duration                      : {end_time - start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.load_balanced:
    print(f"Load-balancer operation duration                        : {lb_end_time - lb_start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.load_balanced_with_api_keys:
    print(f"Load-balancer with API keys operation duration          : {lb_with_api_keys_end_time - lb_with_api_keys_start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.async_load_balanced:
    print(f"Async Load-balancer operation duration                  : {async_lb_end_time - async_lb_start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.async_load_balanced_with_api_keys:
    print(f"Async Load-balancer with API keys operation duration    : {async_lb_with_api_keys_end_time - async_lb_with_api_keys_start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.stream_load_balanced:
    print(f"Stream Load-balancer operation duration                 : {stream_lb_end_time - stream_lb_start_time:>{SECONDS_WIDTH}.2f} seconds")
if test_executions.async_stream_load_balanced:
    print(f"Stream Async Load-balancer operation duration           : {async_stream_lb_end_time - async_stream_lb_start_time:>{SECONDS_WIDTH}.2f} seconds")

print("\n\n")
