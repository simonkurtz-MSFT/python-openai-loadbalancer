from azure.identity import DefaultAzureCredential
from datetime import datetime
from openai import AzureOpenAI, AsyncAzureOpenAI, DefaultHttpxClient, DefaultAsyncHttpxClient, NotFoundError
from load_balancer import AsyncLoadBalancer, LoadBalancer, Backend
from typing import List
import asyncio
import time
import traceback

def token_provider():
    credential = DefaultAzureCredential()
    token = credential.get_token('https://cognitiveservices.azure.com/.default')
    return token.token

# Standard Azure OpenAI Implementation (One Backend)
def send_request(num_of_requests, azure_endpoint: str):
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
def send_loadbalancer_request(num_of_requests, backends: List[Backend]):
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
            except Exception as e:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

async def send_async_loadbalancer_request(num_of_requests, backends: List[Backend]):
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
            except Exception as e:
                print(f"{datetime.now()}: Request failure. Python OpenAI Library has exhausted all of its retries.")
                traceback.print_exc()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()


#############################################################################

# >>> Only make changes to NUM_OF_REQUESTS, MODEL, AZURE_ENDPOINT, and the backends list <<<
NUM_OF_REQUESTS         = 5
MODEL                   = "<your-aoai-model>"  # the model is common across standard and load-balanced requests
AZURE_ENDPOINT          = "https://oai-eastus-xxxxxxxx.openai.azure.com"
backends: List[Backend] = [
    Backend("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-southcentralus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-westus-xxxxxxxx.openai.azure.com", 1)
]

# 1/3: Standard requests to one AOAI backend
print("\nStandard Requests\n-----------------\n")
start_time = time.time()
send_request(NUM_OF_REQUESTS, AZURE_ENDPOINT)
end_time = time.time()

# 2/3: Load-balanced requests to one or more AOAI backends
print("\nLoad Balanced Requests\n----------------------\n")
lb_start_time = time.time()
send_loadbalancer_request(NUM_OF_REQUESTS, backends)
lb_end_time = time.time()

# 3/3: Async Load-balanced requests to one or more AOAI backends
print("\nAsync Load Balanced Requests\n----------------------\n")
async_lb_start_time = time.time()
asyncio.run(send_async_loadbalancer_request(NUM_OF_REQUESTS, backends))
async_lb_end_time = time.time()

# Statistics
print("\n")
print(f"Number of requests                      : {NUM_OF_REQUESTS}")
print(f"Single instance operation duration      : {end_time - start_time:.2f} seconds")
print(f"Load-balancer operation duration        : {lb_end_time - lb_start_time:.2f} seconds")
print(f"Async Load-balancer operation duration  : {async_lb_end_time - async_lb_start_time:.2f} seconds")
print("\n\n")
