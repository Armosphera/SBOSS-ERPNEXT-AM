# Development Dockerfile for SBOSS ERPNEXT AM
# Provides a Frappe bench + all 3 localization apps + the AI layer (Ollama).
# Mount the repo at /workspace for live editing.
#
# Build:   docker build -f infra/docker/dev.Dockerfile -t sboss-dev .
# Run:     docker compose -f infra/compose/dev.yml up

FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BENCH_PATH=/workspace

# System dependencies for Frappe bench + Node + MariaDB client.
# wkhtmltopdf is intentionally NOT installed in the dev image — it's only
# needed at production print-time. For prod, use the official `frappe/erpnext-docker`
# wkhtmltopdf image as a sidecar, or install via the wkhtmltopdf apt repo
# in a prod-only stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        gnupg \
        libffi-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        libmariadb-dev \
        mariadb-client \
        nodejs \
        npm \
        redis-tools \
        sudo \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install frappe-bench CLI (Frappe's own installer)
RUN pip install --upgrade pip wheel && pip install frappe-bench

# Create a non-root user for bench
RUN useradd -m -s /bin/bash -G sudo frappe && echo "frappe ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER frappe
WORKDIR /workspace

# Bootstrap script is mounted at runtime; we just provide a default
COPY --chown=frappe:frappe infra/scripts/bench-init.sh /usr/local/bin/bench-init
RUN sudo chmod +x /usr/local/bin/bench-init

CMD ["/bin/bash"]
