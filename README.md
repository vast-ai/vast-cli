# Vast.ai Python SDK & CLI
[![PyPI version](https://badge.fury.io/py/vastai.svg)](https://badge.fury.io/py/vastai)

The official Vast.ai Python package — provides both the CLI and SDK for managing Vast.ai GPU cloud resources, plus a serverless client for endpoint inference.

## Install

```bash
pip install vastai
```

> **Note:** `pip install vastai-sdk` also works and installs the same package. Both package names are supported for backward compatibility.

## Quickstart

1. Get your API key from [https://cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/)

2. Set your API key:
```bash
vastai set api-key YOUR_API_KEY
```

3. Test a search:
```bash
vastai search offers --limit 3
```
You should see a short list of available GPU offers.

## CLI Usage

The `vastai` command provides full access to the Vast.ai platform from your terminal:

```bash
vastai search offers 'gpu_name=RTX_4090 num_gpus>=4'
vastai create instance 12345 --image pytorch/pytorch --disk 32 --ssh --direct
vastai show instances
vastai stop instance 12345
vastai destroy instance 12345
```

Run `vastai --help` for a full list of commands. You can also use `--help` on any subcommand:

```bash
vastai search offers --help
vastai create instance --help
```

## SDK Usage

```python
from vastai import VastAI

vast = VastAI()  # uses VAST_API_KEY env var, or pass api_key="..."

vast.search_offers(query='gpu_name=RTX_4090 num_gpus>=4')
vast.show_instances()
vast.start_instance(id=12345)
vast.stop_instance(id=12345)
```

Use `help(vast.search_offers)` to view documentation for any method.

> **Migrating from `vastai-sdk`?** The old import still works: `from vastai_sdk import VastAI`

## Using the Serverless Client

1. Create the client
```python
from vastai import Serverless
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

## Tab Completion

Tab completion is supported in Bash and Zsh via [argcomplete](https://github.com/kislyuk/argcomplete) (installed automatically). To enable it:

```bash
activate-global-python-argcomplete
```

Or for a single session:

```bash
eval "$(register-python-argcomplete vastai)"
```

## AI Agents

Vast.ai has a skill for AI coding agents (Claude Code, Cursor, Windsurf, Codex, etc.):

```bash
npx skills add vast-ai/vast-cli
```

This installs the Vast.ai skill so your agent can search offers, create instances, and manage GPU workflows directly. See [CLI SKILL.md](vastai/SKILL.md) or [SDK SKILL.md](vastai_sdk/SKILL.md) for the full reference.

## Contributing

This [repository](https://github.com/vast-ai/vast-cli) is open source. If you find a bug, please [open an issue](https://github.com/vast-ai/vast-cli/issues). PRs are welcome.
