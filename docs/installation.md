# Installation

Vast.ai offers multiple installation methods depending on your use case.

## Standalone Script (wget)

For users who want a single-file solution with minimal dependencies:

```bash
mkdir vastai && cd vastai
wget https://raw.githubusercontent.com/vast-ai/vast-cli/master/vast.py
chmod +x vast.py
```

**Requirements:** Python 3.9.1+, `requests`, `python-dateutil`

```bash
pip install requests python-dateutil
./vast.py --help
```

This method is ideal for:

- Servers without pip access
- Docker containers
- Quick one-off usage

## Package Installation (pip)

For full CLI and SDK access:

```bash
pip install vastai
```

This installs:

- `vastai` CLI command
- `VastAI` SDK class
- All core dependencies

### With Serverless Support

For the async serverless client/server framework:

```bash
pip install "vastai[serverless]"
```

### Full Installation

Install everything including serverless:

```bash
pip install "vastai[all]"
```

### Development Installation

For contributors:

```bash
git clone https://github.com/vast-ai/vast-cli.git
cd vast-cli
pip install -e ".[dev]"
```

## Verify Installation

=== "Standalone"

    ```bash
    ./vast.py --help
    ```

=== "pip"

    ```bash
    vastai --help
    ```

=== "SDK"

    ```python
    from vastai import VastAI
    client = VastAI(api_key="test")
    print(client)  # Should show VastAI instance
    ```

## API Key Setup

After installation, set your API key:

```bash
vastai set api-key YOUR_API_KEY
```

Get your API key from [https://cloud.vast.ai/manage-keys/](https://cloud.vast.ai/manage-keys/).

The key is stored in `~/.config/vastai/vast_api_key` (XDG spec) or `~/.vast_api_key` (legacy).

!!! warning "Keep your API key secure"
    Never commit your API key to version control or share it publicly.

## Optional Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| argcomplete | Tab completion | `pip install argcomplete` |
| borb | PDF invoice generation | `pip install borb` |

## System Requirements

- Python 3.9.1 or higher
- Works on Linux, macOS, and Windows
- Internet connection to reach Vast.ai API

## Troubleshooting

### ImportError for serverless classes

Install serverless extras:
```bash
pip install "vastai[serverless]"
```

### SSL certificate errors

Update certifi:
```bash
pip install --upgrade certifi
```

### Tab completion not working

Ensure argcomplete is installed and activated:
```bash
pip install argcomplete
activate-global-python-argcomplete
```
