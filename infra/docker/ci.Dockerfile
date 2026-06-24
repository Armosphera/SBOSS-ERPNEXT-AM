# CI Dockerfile for SBOSS ERPNEXT AM
# Same as dev but with a pinned ERPNext version for the matrix test job.

ARG ERPNEXT_PIN=15.3.0
FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BENCH_PATH=/workspace \
    ERPNEXT_PIN=${ERPNEXT_PIN}

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl git gnupg \
        libffi-dev libssl-dev libxml2-dev libxslt1-dev libmariadb-dev \
        mariadb-client nodejs npm redis-tools sudo tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip wheel frappe-bench

RUN useradd -m -s /bin/bash -G sudo frappe && echo "frappe ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER frappe
WORKDIR /workspace

COPY --chown=frappe:frappe infra/scripts/bench-init.sh /usr/local/bin/bench-init
RUN sudo chmod +x /usr/local/bin/bench-init

CMD ["/usr/local/bin/bench-init"]
