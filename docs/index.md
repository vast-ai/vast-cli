# Vast.ai CLI & SDK

Welcome to the official documentation for the Vast.ai command-line interface and Python SDK.

## What is Vast.ai?

Vast.ai is a GPU cloud marketplace that connects users with low-cost GPU compute. This package provides three ways to interact with the Vast.ai platform:

- **CLI**: Command-line interface for shell scripts and terminal usage
- **SDK**: Python library for programmatic access
- **Serverless**: Async client/server framework for distributed workloads

## Quick Start

=== "CLI (wget)"

    ```bash
    wget https://raw.githubusercontent.com/vast-ai/vast-cli/master/vast.py
    chmod +x vast.py
    ./vast.py set api-key YOUR_API_KEY
    ./vast.py search offers --limit 3
    ```

=== "CLI (pip)"

    ```bash
    pip install vastai
    vastai set api-key YOUR_API_KEY
    vastai search offers --limit 3
    ```

=== "SDK"

    ```python
    from vastai import VastAI

    client = VastAI(api_key="YOUR_API_KEY")
    offers = client.search_offers()
    print(offers)
    ```

## Features

- **130+ Commands**: Full coverage of the Vast.ai REST API
- **Type Hints**: Complete type annotations for IDE support
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Raw Mode**: JSON output for scripting (`--raw` flag)
- **Serverless Framework**: Async client/server for distributed GPU workloads

## Getting Started

1. [Installation](installation.md) - Set up the CLI, SDK, or both
2. [CLI Guide](cli/index.md) - Learn the command-line interface
3. [SDK Guide](sdk/index.md) - Use the Python SDK
4. [Migration Guide](guides/migration.md) - Upgrading from the old SDK

## Links

- [GitHub Repository](https://github.com/vast-ai/vast-cli)
- [Vast.ai Console](https://vast.ai/console/)
- [API Key](https://cloud.vast.ai/manage-keys/) - Get your API key
