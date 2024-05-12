# Python OpenAI Load Balancer

TL;DR! How do I [start](#getting-started)?

---

Many AI workloads require using more than one Azure OpenAI instance to prioritize Provisioned Throughput Units (PTUs) and insulate themselves from timeouts. In having worked with customers on Azure OpenAI implementations, there are a few common, desired configurations:

1. Use of multiple consumption instances with a round-robin distribution.
1. Prioritize exhaustion of all tokens in a PTU instance with a fallback onto multiple consumption instances.
1. Tiered prioritization of multiple consumption instances (e.g. use instances first that are geographically closer)

While the [OpenAI Python API library](https://github.com/openai/openai-python) respects HTTP 429 and automatically retries after the requested wait period, the library is not set up to support the aforementioned customer desires. The library does, however, allow for the injection of custom httpx clients. This gave rise to this project.

And while there are other Python OpenAI load balancers freely available, I have not seen one yet that addresses the aforementioned scenarios.

Python OpenAI LoadBalancer is injected cleanly into the OpenAI Python API library. The changes between a conventional and a load-balanced Azure OpenAI implementation are few and almost entirely configuration of the backends to be used. You can see a side-by-side example in the [aoai.py](./aoai.py) file in this repo.

## Disclaimer

**This is a pseudo load-balancer.**

When executing this code in parallel, there is no way to distribute requests uniformly across all Azure OpenAI instances. Doing so would require a centralized service, cache, etc. to keep track of a common backends list, but that would also imply a locking mechanism for updates, which would
immediately inhibit the performance benefits of the load balancer. Without knowledge of any other python workers, we can only randomize selection of an available backend.

Furthermore, while the load balancer handles retries across available backends, the [OpenAI Python API library](https://github.com/openai/openai-python) is not fully insulated from failing on multiple HTTP 429s when all backends are returning HTTP 429s. It is advised to load-test with multiple concurrent python workers to understand how your specific Azure OpenAI instances, your limits, and your load balancer configuration function.

## Attribution

This project would not have been possible without the incredible work that [@andredewes](https://github.com/andredewes) has done with his [Smart Load Balancing for OpenAI Endpoints and Azure API Management](https://github.com/Azure-Samples/openai-apim-lb). If you use Azure API Management in your infrastructure, I highly recommend you consider his policy.

## Current Limitations

- Python OpenAI Load Balancer is primarily target for Azure OpenAI; however, it can be expanded upon to serve OpenAI endpoints as well.
- Async is not yet supported.
- My development setup is based on Windows and Powershell. I have not tried this with Linux.

## Prerequisites

It helps to have some familiarity with how the [OpenAI Python API library](https://github.com/openai/openai-python) works. If you have used it before, then the code in `aoai.py` here will look very familiar to you.
It's also good to have some knowledge of authentication and identities.

## Authentication

Locally, you can log into Azure via the CLI and the steps below and use the `AzureDefaultCredential` (what I use in my example). In Azure, you'd want to use a managed identity for your application. It's best to avoid using the Azure OpenAI instances' keys as that could a) accidentally leave credentials in your source code, and b) the keys are different for each instance, which would probably require expanding upon the `Backends` class. Best to just avoid keys.

## Single Requestor Model

I started with a single0requestor model to experiment with the algorithm to select backends. This is nota model that would typically be employed as almost every workload would run multiple python workers in parallel. Nevertheless, I left the files in the repo with the `single-requestor` suffix.

## Getting Started

### Cloning the repo & Preparing the python environment

1. Clone the repo.
1. Open the cloned repo folder in VS Code.
1. Open a terminal session in VS Code.
1. Run [setup-python.ps1](./setup-python.ps1) to prepare the python environment.

### Configuration

For the load-balanced approach, please use the same model across all instances.

1. Open [aoai.py](./aoai.py).
1. Replace `<your-aoai-model>` with the Azure OpenAI model.
1. Replace `<your-aoai-instance>` with the primary/single Azure OpenAI instance.
1. Replace `<your-aoai-instance-1>`, `<your-aoai-instance-2>`, `<your-aoai-instance-3>` with all the Azure OpenAI instances you want to load-balance across. Delete entries you don't need. See [Load Balancer Configuration](#load-balancer-configuration) for details.
1. Replace the value for variable `num_of_requests` with the number of requests you wish to execute.

### Credentials

Locally, your AzuredefaultCredential is used. Each Azure OpenAI instance must be set up with `Cognitive Services OpenAI User` role assignment for your Azure credential (your identity post-login). This ensures that you can use your credential across all Azure OpenAI instances.

When running in Azure, it's advised to use managed identities.

1. Log in with `az login`.

## Execution

1. Run [python-aoai.ps1](.\python-aoai.ps1) just once to see it execute properly.
1. Run [python-aoai.ps1](.\python-aoai.ps1) concurrently in multiple terminals to simulate parallel requests from multiple python workers.

## Distribution of Requests

### Across Different Priorities

- Priority 1, when available, will always supersede priority 2.
- Priority 2, when available, will always supersede an unavailable priority 1.
- Priority 3, when available, will always supersede unavailable priorities 1 & 2.

### Across Multiple Backends of Same Priority

There is no likelihood of a uniform distribution across available endpoints when running multiple python workers in parallel. The selection is randomized.

In the single-requestor model, the distribution of attempts over available backends should be fairly uniform for backends of the same priority.

## Backoff & Retries

When no backends are available (e.g. all timed out), Python OpenAI Load Balancer returns the soonest retry in seconds determined based on the `retry_after` value on each backend.
You may see in the logs that there is a curious delay after the load balancer returns and the next request comes in. The OpenAI Python library [uses a short exponential backoff](https://github.com/openai/openai-python?tab=readme-ov-file#retries) in addition to the `Retry-After` header value. This seems to be a bit overkill.

In this log excerpt, we see that all three backends are timing out. As the standard behavior returns an HTTP 429 from a single backend, we do the same here with the load-balanced approach. This allows the OpenAI Pythong library to handle the HTTP 429 that it believes it received from a singular backend.
The wait periods are 44 seconds (westus), 4 seconds (eastus), and 7 seconds (southcentralus) in this log. Our logic determines that eastus will become available soonest. Therefore, we return a `Retry-After` header with a value of `4`. The OpenAI Python library then adds its exponential backoff (~2 seconds here).

```text
2024-05-11 00:56:32.299477:   Request sent to server: https://oai-westus-20240509.openai.azure.com/openai/deployments/gpt-35-turbo-sjk-001/chat/completions?api-version=2024-04-01-preview, Status Code: 429 - FAIL
2024-05-11 00:56:32.299477:   Backend oai-westus-20240509.openai.azure.com is throttling. Retry after 44 second(s).
2024-05-11 00:56:32.394350:   Request sent to server: https://oai-eastus-20240509.openai.azure.com/openai/deployments/gpt-35-turbo-sjk-001/chat/completions?api-version=2024-04-01-preview, Status Code: 429 - FAIL
2024-05-11 00:56:32.395578:   Backend oai-eastus-20240509.openai.azure.com is throttling. Retry after 4 second(s).
2024-05-11 00:56:32.451891:   Request sent to server: https://oai-southcentralus-20240509.openai.azure.com/openai/deployments/gpt-35-turbo-sjk-001/chat/completions?api-version=2024-04-01-preview, Status Code: 429 - FAIL
2024-05-11 00:56:32.452883:   Backend oai-southcentralus-20240509.openai.azure.com is throttling. Retry after 7 second(s).
2024-05-11 00:56:32.452883:   No backends available. Exiting.
2024-05-11 00:56:32.453891:   Soonest Retry After: oai-eastus-20240509.openai.azure.com - 4 second(s)
2024-05-11 00:56:38.551672:   Backend oai-eastus-20240509.openai.azure.com is no longer throttling.
2024-05-11 00:56:39.851076:   Request sent to server: https://oai-eastus-20240509.openai.azure.com/openai/deployments/gpt-35-turbo-sjk-001/chat/completions?api-version=2024-04-01-preview, Status code: 200
```

## Load Balancer Configuration

At its core, the Load Balancer configuration requires one or more backend hosts and a numeric priority starting at 1. Please take note that you define a host, not a URL.

I use a total of three Azure OpenAI instances in three regions. These instances are set up with intentionally small tokens-per-minute (tpm) to trigger HTTP 429s.
The standard approach never changes and uses the same host (first in the backend list), which provides a stable comparison to the load-balanced approach.
While the number of requests differs per tests below, we issue the same number of requests against standard and load-balanced approaches.

### One Backend

This is logically equivalent to what the standard approach does. This configuration does not provide value over the standard approach.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus-xxxxxxxx.openai.azure.com", 1)
]
```

### Two Backends with Same Priority

Load-balancing evenly between Azure OpenAI instances hedges you against being stalled due to a 429 from a single instance.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backends("oai-southcentralus-xxxxxxxx.openai.azure.com", 1)
]
```

### Three Backends with Same Priority

Adding a third backend with same priority exacerbates the difference to the standard approach further. Here, we need to use 20 requests to incur more HTTP 429s.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backends("oai-southcentralus-xxxxxxxx.openai.azure.com", 1),
    Backends("oai-westus-xxxxxxxx.openai.azure.com", 1)
]
```

### Three Backends with Two Different Priorities

The most common reason for this approach may well be the prioritization of Provisioned Throughput Units (PTUs). This is a reserved capacity over a period of time that is billed at that reservation and not flexible as consumption instances. Aside from guaranteed capacity, latency is also much more stable. Naturally, this is an instance that you would want to prioritize over all others but allow yourself to have fallbacks if you burst over what the PTU provides.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backends("oai-southcentralus-xxxxxxxx.openai.azure.com", 2),
    Backends("oai-westus-xxxxxxxx.openai.azure.com", 2)
]
```

### Three Backends with Three Different Priorities

An example of this setup may be that most of your assets reside in one region (e.g. East US). It stands to reason that you want to use the Azure OpenAI instance in that region. To hedge yourself against HTTP 429s, you decide to add a second region that's geographically close (e.g. East US 2) as well as a third (e.g. West US).

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus-xxxxxxxx.openai.azure.com", 1),
    Backends("oai-southcentralus-xxxxxxxx.openai.azure.com", 2),
    Backends("oai-westus-xxxxxxxx.openai.azure.com", 3)
]
```
