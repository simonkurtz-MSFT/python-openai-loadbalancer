# Python OpenAI Load Balancer

Many AI workloads require using more than one Azure OpenAI instance to prioritize Provisioned Throughput Units (PTUs) and insulate themselves from timeouts. In having worked with customers on Azure OpenAI implementations, there are a few common, desired configurations:

1. Use of multiple consumption instances with a round-robin distribution.
1. Prioritize exhaustion of all tokens in a PTU instance with a fallback onto multiple consumption instances.
1. Tiered prioritization of multiple consumption instances (e.g. use instances first that are geographically closer)

While the [OpenAI Python API library](https://github.com/openai/openai-python) respects HTTP 429 and automatically retries after the requested wait period, the library is not set up to support the aforementioned customer desires. The library does, however, allow for the injection of custom httpx clients. This gave rise to this project.

Python OpenAI LoadBalancer is injected cleanly into the OpenAI Python API library. The changes between a conventional and a load-balanced Azure OpenAI implementation are few and almost entirely configuration of the backends to be used. You can see a side-by-side example in the `aoai.py` file in this repo.

## Attribution

This project would not have been possible without the incredible work that [@andredewes](https://github.com/andredewes) has done with his [Smart Load Balancing for OpenAI Endpoints and Azure API Management](https://github.com/Azure-Samples/openai-apim-lb). If you use Azure API Management in your infrastructure, I highly recommend you consider his policy.

## Current Limitations

- Python OpenAI Load Balancer is primarily target for Azure OpenAI; however, it can be expanded upon to serve OpenAI endpoints as well.
- Async is not yet supported.
- My development setup is based on Windows and Powershell. I have not tried this with Linux.

## Contributions

Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## Setup

### Cloning the repo & Preparing the python environment

1. Clone the repo
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
