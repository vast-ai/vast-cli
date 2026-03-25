# Docker Setup for PyWorker

This setup allows you to run the PyWorker with the vast-sdk in a containerized environment.

## Quick Start

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` to configure branches** (optional):
   ```bash
   # Use the current development branch
   SDK_BRANCH=candidate-0.4.2
   PYWORKER_BRANCH=main
   PYWORKER_REF=main
   ```

3. **Build and run**:
   ```bash
   docker-compose up --build --force-recreate
   ```

The worker will be available at `http://localhost:3001`

## Configuration Variables

### SDK_BRANCH
- **Default**: `main`
- **Purpose**: Specifies which branch/tag/commit of [vast-ai/vast-sdk](https://github.com/vast-ai/vast-sdk) to install
- **Example**: `SDK_BRANCH=candidate-0.4.2`

The pyworker's `start_server.sh` will install the SDK using:
```bash
uv pip install "vastai-sdk @ git+https://github.com/vast-ai/vast-sdk.git@${SDK_BRANCH}"
```

### PYWORKER_BRANCH
- **Default**: `main`
- **Purpose**: Specifies which branch of [vast-ai/pyworker](https://github.com/vast-ai/pyworker) to fetch `start_server.sh` from
- **Example**: `PYWORKER_BRANCH=develop`

This determines which version of the startup script is used.

### PYWORKER_REF
- **Default**: `main`
- **Purpose**: Git reference (branch/tag/commit) to checkout when cloning the pyworker repository
- **Example**: `PYWORKER_REF=v1.0.0`

This is used inside `start_server.sh` when it clones the pyworker code.

## How It Works

### 1. Build Time
- Dockerfile creates a wrapper script at `/usr/local/bin/start_server_wrapper.sh`
- The wrapper is configured with the `PYWORKER_BRANCH` build argument

### 2. Runtime
When the container starts:
1. The wrapper script fetches `start_server.sh` from the specified `PYWORKER_BRANCH`
2. The fetched script is executed with all environment variables
3. `start_server.sh` then:
   - Installs the vast-sdk from the specified `SDK_BRANCH`
   - Clones pyworker repository at `PYWORKER_REF`
   - Sets up the Python environment
   - Launches the worker

## Examples

### Development with latest SDK changes
```bash
# .env
SDK_BRANCH=candidate-0.4.2
PYWORKER_BRANCH=main
PYWORKER_REF=main
```

### Testing a specific pyworker version
```bash
# .env
SDK_BRANCH=main
PYWORKER_BRANCH=v1.2.3
PYWORKER_REF=v1.2.3
```

### Override via command line
```bash
SDK_BRANCH=candidate-0.4.2 PYWORKER_BRANCH=develop docker-compose up --build
```

## Troubleshooting

### "Failed to fetch start_server.sh from branch X"
- The specified `PYWORKER_BRANCH` doesn't exist in the pyworker repository
- Check the branch name at https://github.com/vast-ai/pyworker

### "Failed to install vastai-sdk from vast-ai/vast-sdk@X"
- The specified `SDK_BRANCH` doesn't exist in the vast-sdk repository
- Check the branch name at https://github.com/vast-ai/vast-sdk

### Container exits immediately
Check the logs:
```bash
docker-compose logs test-container
```

Look for:
- Missing required environment variables
- Python import errors
- Network issues fetching dependencies

### View worker logs inside container
```bash
docker exec -it test-container cat /workspace/debug.log
docker exec -it test-container cat /workspace/pyworker.log
```

## Migration from Old Setup

### If you had a local start_server.sh
The Dockerfile now fetches `start_server.sh` directly from GitHub, so any local version is no longer used.

### If you used SDK_VERSION
Replace with `SDK_BRANCH`:
- **Old**: `SDK_VERSION=0.4.2.dev1`
- **New**: `SDK_BRANCH=candidate-0.4.2`

The new approach installs directly from the GitHub repository at the specified branch.
