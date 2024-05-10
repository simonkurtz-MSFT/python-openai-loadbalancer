# Python OpenAI LoadBalancer

## Windows & Powershell

### Setup

#### Cloning the repo & Preparing the python environment

1. Clone the repo
1. Open the cloned repo folder in VS Code.
1. Open a terminal session in VS Code.
1. Run `.\setup-python.ps1` to prepare the python environment.

#### Configuration

For the load-balanced approach, please use the same model across all instances.

1. Open `.\aoai.py`.
1. Replace `<your-aoai-model>` with the Azure OpenAI model.
1. Replace `<your-aoai-instance>` with the primary/single Azure OpenAI instance.
1. Replace `<your-aoai-instance-1>`, `<your-aoai-instance-2>`, `<your-aoai-instance-3>` with all the Azure OpenAI instances you want to load-balance across.
1. Replace the value for variable `num_of_requests` with the number of requests you wish to execute.

#### Credentials

Locally, your AzuredefaultCredential is used. Each Azure OpenAI instance must be set up with `Cognitive Services OpenAI User` role assignment for your Azure credential (your identity post-login). This ensures that you can use your credential across all Azure OpenAI instances.

When running in Azure, it's advised to use managed identities.

1. Log in with `az login`.

### Execution

1. Run `.\python-aoai.ps1`.
