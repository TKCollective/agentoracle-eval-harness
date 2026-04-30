# AgentOracle Eval Harness — Reproducible Dockerfile
#
# Matches the FEVER 2024 shared task reference VM:
#   - Base: Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)
#   - GPU target: Nvidia A10G (g5.2xlarge)
#   - 32GB RAM, 8 vCPUs, 450GB storage
#
# AgentOracle is a hosted API, so this image does not need GPU at all unless
# running the local LLM grader. For most users, the default OpenRouter-hosted
# Llama 3.3 70B grader is sufficient and the image runs on any modern CPU.

FROM ubuntu:22.04

LABEL org.opencontainers.image.source="https://github.com/TKCollective/agentoracle-eval-harness"
LABEL org.opencontainers.image.title="AgentOracle Eval Harness"
LABEL org.opencontainers.image.description="Reproducible benchmark harness against FEVER + AVeriTeC for AgentOracle's /evaluate endpoint"
LABEL org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3-pip python3.11-venv \
        curl ca-certificates git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/eval-harness

# Pin Python deps for reproducibility
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY src/      ./src/
COPY scripts/  ./scripts/
COPY docs/     ./docs/

# Mount points (provided at runtime)
#   /data    — datasets (FEVER + AVeriTeC)
#   /results — output writes here
VOLUME ["/data", "/results"]

# Default seed for deterministic runs
ENV SEED=42

ENTRYPOINT ["bash"]
CMD ["./scripts/run_full_eval.sh"]
