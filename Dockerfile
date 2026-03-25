# Base image with Python 3.10 and Debian/Ubuntu userland
FROM python:3.10-slim

# Install dependencies needed by the worker script
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        openssl \
        bash \
    && rm -rf /var/lib/apt/lists/*

# Build argument for pyworker branch
ARG PYWORKER_BRANCH=main

# Default envs (can be overridden at `docker run`)
ENV WORKSPACE_DIR=/workspace \
    REPORT_ADDR=https://run.vast.ai \
    USE_SSL=true \
    WORKER_PORT=3000 \
    PYTHONUNBUFFERED=1 \
    PYWORKER_BRANCH=${PYWORKER_BRANCH}


# Create a wrapper script that fetches start_server.sh at runtime with the correct branch
RUN echo '#!/bin/bash' > /usr/local/bin/start_server_wrapper.sh && \
    echo 'set -e' >> /usr/local/bin/start_server_wrapper.sh && \
    echo 'PYWORKER_BRANCH="${PYWORKER_BRANCH:-main}"' >> /usr/local/bin/start_server_wrapper.sh && \
    echo 'echo "Fetching start_server.sh from pyworker branch: $PYWORKER_BRANCH"' >> /usr/local/bin/start_server_wrapper.sh && \
    echo 'curl -fsSL "https://raw.githubusercontent.com/vast-ai/pyworker/${PYWORKER_BRANCH}/start_server.sh" -o /tmp/start_server.sh || {' >> /usr/local/bin/start_server_wrapper.sh && \
    echo '  echo "ERROR: Failed to fetch start_server.sh from branch $PYWORKER_BRANCH"' >> /usr/local/bin/start_server_wrapper.sh && \
    echo '  exit 1' >> /usr/local/bin/start_server_wrapper.sh && \
    echo '}' >> /usr/local/bin/start_server_wrapper.sh && \
    echo 'chmod +x /tmp/start_server.sh' >> /usr/local/bin/start_server_wrapper.sh && \
    echo 'exec /bin/bash /tmp/start_server.sh' >> /usr/local/bin/start_server_wrapper.sh && \
    chmod +x /usr/local/bin/start_server_wrapper.sh

# Run the wrapper script which fetches and executes start_server.sh
ENTRYPOINT ["/bin/bash", "/usr/local/bin/start_server_wrapper.sh"]
