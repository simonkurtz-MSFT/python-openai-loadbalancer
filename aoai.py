from azure.identity import DefaultAzureCredential # type: ignore
from datetime import datetime
from openai import AzureOpenAI, DefaultHttpxClient, NotFoundError
from load_balancer import LoadBalancer, Backend
from typing import List
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
def send_loadbalancer_request(num_of_requests, backends: Backend):
    try:
        # Instantiate the LoadBalancer class and create a new https client with the LoadBalancer as the injected transport
        lb = LoadBalancer(backends)

        client = AzureOpenAI(
            azure_endpoint = f"https://{backends[0].host}",   # Must be seeded, so we use the first host. It will get overwritten by the LoadBalancer
            azure_ad_token_provider = token_provider,
            api_version = "2024-04-01-preview",
            http_client = DefaultHttpxClient(transport=lb)    # Inject the LoadBalancer as the transport in a new default httpx client
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

#############################################################################

# >>> Only make changes to MODEL, AZURE_ENDPOINT, and the backends list <<<



# Common Constants
NUM_OF_REQUESTS = 5
MODEL = "<your-aoai-model>"  # the model is common across standard and load-balanced requests

# Standard requests to one AOAI backend
AZURE_ENDPOINT = "https://oai-eastus-xxxxxxxx.openai.azure.com"
start_time = time.time()

send_request(NUM_OF_REQUESTS, AZURE_ENDPOINT)
end_time = time.time()

# Load-balanced requests to one or more AOAI backends
# Define the backends and their priority
backends: List[Backend] = [
    Backend("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-southcentralus-xxxxxxxx.openai.azure.com", 1),
    Backend("oai-westus-xxxxxxxx.openai.azure.com", 1)
]
lb_start_time = time.time()
send_loadbalancer_request(NUM_OF_REQUESTS, backends)
lb_end_time = time.time()

# Statistics
print("\n")
print(f"Number of requests                 : {NUM_OF_REQUESTS}")
print(f"Single instance operation duration : {end_time - start_time:.2f} seconds")
print(f"Load-balancer operation duration   : {lb_end_time - lb_start_time:.2f} seconds")
print("\n\n")
