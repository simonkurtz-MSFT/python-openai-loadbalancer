# Python OpenAI Load Balancer

Many AI workloads require using more than one Azure OpenAI instance to prioritize Provisioned Throughput Units (PTUs) and insulate themselves from timeouts. In having worked with customers on Azure OpenAI implementations, there are a few common, desired configurations:

1. Use of multiple consumption instances with a round-robin distribution.
1. Prioritize exhaustion of all tokens in a PTU instance with a fallback onto multiple consumption instances.
1. Tiered prioritization of multiple consumption instances (e.g. use instances first that are geographically closer)

While the [OpenAI Python API library](https://github.com/openai/openai-python) respects HTTP 429 and automatically retries after the requested wait period, the library is not set up to support the aforementioned customer desires. The library does, however, allow for the injection of custom httpx clients. This gave rise to this project.

Python OpenAI LoadBalancer is injected cleanly into the OpenAI Python API library. The changes between a conventional and a load-balanced Azure OpenAI implementation are few and almost entirely configuration of the backends to be used. You can see a side-by-side example in the `aoai.py` file in this repo.

## Attribution

This project would not have been possible without the incredible work that [@andredewes](https://github.com/andredewes) has done with his [Smart Load Balancing for OpenAI Endpoints and Azure API Management](https://github.com/Azure-Samples/openai-apim-lb). If you use Azure API Management in your infrastructure, I highly recommend you consider his policy.

## Prerequisites

It helps to have some familiarity with how the [OpenAI Python API library](https://github.com/openai/openai-python) works. If you have used it before, then the code in `aoai.py` here will look very familiar to you.
It's also good to have some knowledge of authentication and identities.

## Authentication

Locally, you can log into Azure via the CLI and the steps below and use the `AzureDefaultCredential` (what I use in my example). In Azure, you'd want to use a managed identity for your application. It's best to avoid using the Azure OpenAI instances' keys as that could a) accidentally leave credentials in your source code, and b) the keys are different for each instance, which would probably require expanding upon the `Backends` class. Best to just avoid keys.

## Current Limitations

- Python OpenAI Load Balancer is primarily target for Azure OpenAI; however, it can be expanded upon to serve OpenAI endpoints as well.
- Async is not yet supported.
- My development setup is based on Windows and Powershell. I have not tried this with Linux.
- Pseudo-load balancing (not exactly uniform).

## Contributions

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## Setup

### Cloning the repo & Preparing the python environment

1. Clone the repo.
1. Open the cloned repo folder in VS Code.
1. Open a terminal session in VS Code.
1. Run `.\setup-python.ps1` to prepare the python environment.

### Configuration

For the load-balanced approach, please use the same model across all instances.

1. Open `.\aoai.py`.
1. Replace `<your-aoai-model>` with the Azure OpenAI model.
1. Replace `<your-aoai-instance>` with the primary/single Azure OpenAI instance.
1. Replace `<your-aoai-instance-1>`, `<your-aoai-instance-2>`, `<your-aoai-instance-3>` with all the Azure OpenAI instances you want to load-balance across.
1. Replace the value for variable `num_of_requests` with the number of requests you wish to execute.

### Credentials

Locally, your AzuredefaultCredential is used. Each Azure OpenAI instance must be set up with `Cognitive Services OpenAI User` role assignment for your Azure credential (your identity post-login). This ensures that you can use your credential across all Azure OpenAI instances.

When running in Azure, it's advised to use managed identities.

1. Log in with `az login`.

## Execution

1. Run `.\python-aoai.ps1`.

## Distribution of Requests

### Across Different Priorities

- Priority 1, when available, will always supersede priority 2.
- Priority 2, when available, will always supersede an unavailable priority 1.
- Priority 3, when available, will always supersede unavailable priorities 1 & 2.

### Across Multiple Backends of Same Priority

While desirable, we are not presently achieving a uniform distribution across same priorities. This largely has to do with the available backends array changing in size, making it a quasi moving target to distribute across. To a lesser degree, the `random` module may also affect the distribution.

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
    Backends("oai-eastus.openai.azure.com", 1)
]
```

This comparison is as close to apples-to-apples between standard and load-balanced approaches as we can get. The time for 10 requests is fairly similar and differs a bit due to when 429s may be incurred.
While the number of requests is set to 10, the Load Balancer experiences five failures (i.e. HTTP 429) and ends up making a total of 15 requests to successfully satisfy 10 requested ones. Note that the python OpenAI API library has no knowledge of this (nor does it need to).

```text
Load Balancer Statistics:

Total Requests  : 15
Total Successes : 10
Total Failures  :  5

Backend                       Successes  Failures
-------------------------------------------------
oai-eastus.openai.azure.com          10         5


*************************************************


Number of requests                 : 10
Single instance operation duration : 57.54 seconds
Load-balancer operation duration   : 61.47 seconds
```

### Two Backends with Same Priority

Load-balancing evenly between Azure OpenAI instances hedges you against being stalled due to a 429 from a single instance.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus.openai.azure.com", 1),
    Backends("oai-southcentralus.openai.azure.com", 1)
]
```

Over this very small sample size, with the load-balanced approach, a fairly linear distribution occurred over both Azure OpenAI endpoints. Take particular note of the duration of 10 requests. While the standard approach duration nearly matches our first configuration above, the load-balanced approach is significantly faster. Due to the intentionally low token-per-minute limit, the standard approach incurs HTTP 429s and consequently respects the `retry-after` before it attempts a retry. However, Load Balancer, upon any one failure from the backend, will automatically and immediately retry if an available backend is available. This eliminates significant wait!

```text
Load Balancer Statistics:

Total Requests  : 14
Total Successes : 10
Total Failures  :  4

Backend                               Successes  Failures
---------------------------------------------------------
oai-eastus.openai.azure.com                   4         3
oai-southcentralus.openai.azure.com           6         1


*********************************************************


Number of requests                 : 10
Single instance operation duration : 55.65 seconds
Load-balancer operation duration   : 32.95 seconds
```

### Three Backends with Same Priority

Adding a third backend with same priority exacerbates the difference to the standard approach further. Here, we need to use 20 requests to incur more HTTP 429s.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus.openai.azure.com", 1),
    Backends("oai-southcentralus.openai.azure.com", 1),
    Backends("oai-westus.openai.azure.com", 1)
]
```

Requests are now issued across three instances. The randomization did not yield as linear of a distribution, but the sample size is still relatively small. Again, note the difference in duration between the standard and load-balanced approach!

```text
Load Balancer Statistics:

Total Requests  : 26
Total Successes : 20
Total Failures  :  6

Backend                               Successes  Failures
---------------------------------------------------------
oai-westus.openai.azure.com                   1         2
oai-southcentralus.openai.azure.com          10         2
oai-eastus.openai.azure.com                   9         2


*********************************************************


Number of requests                 : 20
Single instance operation duration : 117.44 seconds
Load-balancer operation duration   : 69.06 seconds
```

### Three Backends with Two Different Priorities

The most common reason for this approach may well be the prioritization of Provisioned Throughput Units (PTUs). This is a reserved capacity over a period of time that is billed at that reservation and not flexible as consumption instances. Aside from guaranteed capacity, latency is also much more stable. Naturally, this is an instance that you would want to prioritize over all others but allow yourself to have fallbacks if you burst over what the PTU provides.

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus.openai.azure.com", 1),
    Backends("oai-southcentralus.openai.azure.com", 2),
    Backends("oai-westus.openai.azure.com", 2)
]
```

A clear trend towards the backend with priority 1 is noticeable. The five failures that priority 1 inccurred were then retried on the two priority 2 backends.

```text
Load Balancer Statistics:

Total Requests  : 25
Total Successes : 20
Total Failures  :  5

Backend                               Successes  Failures
---------------------------------------------------------
oai-eastus.openai.azure.com                  15         5
oai-southcentralus.openai.azure.com           4         0
oai-westus.openai.azure.com                   1         0


*********************************************************


Number of requests                 : 20
Single instance operation duration : 80.03 seconds
Load-balancer operation duration   : 59.71 seconds
```

### Three Backends with Three Different Priorities

An example of this setup may be that most of your assets reside in one region (e.g. East US). It stands to reason that you want to use the Azure OpenAI instance in that region. To hedge yourself against HTTP 429s, you decide to add a second region that's geographically close (e.g. East US 2) as well as a third (e.g. West US).

```python
# Define the backends and their priority
backends = [
    Backends("oai-eastus.openai.azure.com", 1),
    Backends("oai-southcentralus.openai.azure.com", 2),
    Backends("oai-westus.openai.azure.com", 3)
]
```

Even though I had three backends defined, my sequential load tests from one machine did not levy significant enough load to where both priority 1 and 2 were unavailable at the same time. You can see the bias towards the priority 1 backend with 37 successes while all 13 failures (429s) were handled by the priority 2 backend.

```text
Load Balancer Statistics:

Total Requests  : 63
Total Successes : 50
Total Failures  : 13

Backend                               Successes  Failures
---------------------------------------------------------
oai-eastus.openai.azure.com                  37        13
oai-southcentralus.openai.azure.com          13         0


*********************************************************


Number of requests                 : 50
Single instance operation duration : 204.01 seconds
Load-balancer operation duration   : 148.52 seconds
```
