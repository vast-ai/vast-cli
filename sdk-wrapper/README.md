# Vast.ai Python SDK

> **This package is deprecated.** It has been merged into [vast-ai/vast-cli](https://github.com/vast-ai/vast-cli). `pip install vastai` now installs both the SDK and CLI in a single package. `pip install vastai-sdk` still works and installs the same package. For issues and PRs, go to [vast-ai/vast-cli](https://github.com/vast-ai/vast-cli).

## Install

```bash
pip install vastai-sdk
```

## Quickstart

1. Get your API key from [https://cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/)

2. Set your API key:
```python
from vastai_sdk import VastAI
vast = VastAI(api_key="YOUR_API_KEY")
```

Or set the `VAST_API_KEY` environment variable and just use:
```python
vast = VastAI()
```

## SDK Usage

```python
from vastai_sdk import VastAI

vast = VastAI()

vast.search_offers(query='gpu_name=RTX_4090 num_gpus>=4')
vast.show_instances()
vast.start_instance(id=12345)
vast.stop_instance(id=12345)
```

Use `help(vast.search_offers)` to view documentation for any method.

## Using the Serverless Client

1. Create the client
```python
from vastai_sdk.serverless.client.client import Serverless
serverless = Serverless() # or, Serverless("YOUR_API_KEY")
```
2. Get an endpoint
```python
endpoint = await serverless.get_endpoint("my-endpoint")
```
3. Make a request
```python
request_body = {
    "model": "Qwen/Qwen3-8B",
    "prompt" : "Who are you?",
    "max_tokens" : 100,
    "temperature" : 0.7
}
response = await serverless.request("/v1/completions", request_body)
```
4. Read the response
```python
text = response["response"]["choices"][0]["text"]
print(text)
```

Find more examples in the `examples/` directory.

## Contributing

This repo is deprecated. For issues, PRs, and documentation, go to [vast-ai/vast-cli](https://github.com/vast-ai/vast-cli).
