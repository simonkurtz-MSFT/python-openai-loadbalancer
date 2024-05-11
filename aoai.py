from azure.identity import DefaultAzureCredential # type: ignore
from datetime import datetime
from openai import AzureOpenAI, DefaultHttpxClient, NotFoundError
from load_balancer import LoadBalancer, Backends
import time
import traceback

def token_provider():
    credential = DefaultAzureCredential()
    token = credential.get_token('https://cognitiveservices.azure.com/.default')    
    return token.token

# Standard Azure OpenAI Implementation (One Backend)
def send_request(numOfRequests):
    try:
        client = AzureOpenAI(
            azure_endpoint="https://<your-aoai-instance>.openai.azure.com",
            azure_ad_token_provider=token_provider,
            api_version="2024-04-01-preview"
        )

        for i in range(numOfRequests):
            print(f"{datetime.now()}: Standard request {i+1}/{numOfRequests}")
        
            response = client.chat.completions.create(
                model="<your-aoai-model>",
                messages=[
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
def send_loadbalancer_request(numOfRequests):
    try:
        # Define the backends and their priority
        backends = [
            Backends("<your-aoai-instance-1>.openai.azure.com", 1),
            Backends("<your-aoai-instance-2>.openai.azure.com", 1),
            Backends("<your-aoai-instance-3>.openai.azure.com", 1)
        ]

        # Instantiate the LoadBalancer class and create a new https client with the LoadBalancer as the injected transport
        lb = LoadBalancer(backends)        

        client = AzureOpenAI(
            azure_endpoint=f"https://{backends[0].host}",   # Must be seeded, so we use the first host. It will get overwritten by the LoadBalancer
            azure_ad_token_provider=token_provider,
            api_version="2024-04-01-preview",
            http_client = DefaultHttpxClient(transport=lb)  # Inject the LoadBalancer as the transport in a new default httpx client
        )

        for i in range(numOfRequests):
            print(f"{datetime.now()}: LoadBalancer request {i+1}/{numOfRequests}")
        
            response = client.chat.completions.create(
                model="<your-aoai-model>",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"}
                ]
            )

            print(f"{datetime.now()}:\n{response}\n\n\n")

        # Print LoadBalancer Statistics
        lb.statistics.print()

    except NotFoundError as e:
        print("openai.NotFoundError:", vars(e))
        traceback.print_exc()
    except Exception as e:
        print("Exception:", vars(e))
        traceback.print_exc()

#############################################################################

num_of_requests = 5

# Standard requests to one AOAI backend
start_time = time.time()
send_request(num_of_requests)
end_time = time.time()

# Load-balanced requests to one or more AOAI backends
lb_start_time = time.time()
send_loadbalancer_request(num_of_requests)
lb_end_time = time.time()

print("\n")
print(f"Number of requests                 : {num_of_requests}")
print(f"Single instance operation duration : {end_time - start_time:.2f} seconds")
print(f"Load-balancer operation duration   : {lb_end_time - lb_start_time:.2f} seconds")
print("\n\n")