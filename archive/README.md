# Python OpenAI Load Balancer

## Single Requestor Model

I started with a single-requestor model to experiment with the algorithm to select backends. This model is not typically used, as most workloads run multiple Python workers in parallel. Nevertheless, I left the files in the repo with the `single-requestor` suffix for reference.
