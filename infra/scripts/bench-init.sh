#!/usr/bin/env bash
# bench-init.sh — initialize a bench + ERPNext + HRMS + our 3 apps
# inside the dev container. Idempotent: safe to re-run.

set -euo pipefail

WORKSPACE="${BENCH_PATH:-/workspace}"
cd "$WORKSPACE"

# 1. Initialize bench if not present
if [[ ! -d "frappe-bench" ]]; then
  echo "==> Initializing bench (Frappe v15.3.0)"
  bench init --frappe-branch v15.3.0 --python python3.11 frappe-bench
fi

cd "$WORKSPACE/frappe-bench"

# 2. Configure MariaDB + Redis to point at the compose services
bench set-config -p db_host mariadb || true
bench set-config -p redis_cache redis://redis:6379 || true
bench set-config -p redis_queue redis://redis:6379 || true
bench set-config -p redis_socketio redis://redis:6379 || true
bench set-config -p socketio_port 9000 || true

# 3. Get ERPNext + HRMS
if [[ ! -d "apps/erpnext" ]]; then
  echo "==> Getting ERPNext"
  bench get-app erpnext --branch v15.3.0
fi
if [[ ! -d "apps/hrms" ]]; then
  echo "==> Getting Frappe HRMS"
  bench get-app hrms --branch v15.0.0
fi

# 4. Get our 3 localization apps from this monorepo.
# Use --resolve to avoid asking interactively; apps are local (not from git).
if [[ ! -d "apps/frappe_armenia" ]]; then
  echo "==> Getting frappe_armenia (local)"
  bench get-app /workspace/apps/frappe_armenia --resolve
fi
if [[ ! -d "apps/frappe_uae" ]]; then
  echo "==> Getting frappe_uae (local)"
  bench get-app /workspace/apps/frappe_uae --resolve
fi
if [[ ! -d "apps/frappe_ai_local" ]]; then
  echo "==> Getting frappe_ai_local (local)"
  bench get-app /workspace/apps/frappe_ai_local --resolve
fi

# 5. Install shared libs (one-time)
if [[ ! -f "/workspace/.libs-installed" ]]; then
  echo "==> Installing shared libs (MIT)"
  pip install -e /workspace/libs/frappe_localization_core
  pip install -e /workspace/libs/frappe_payroll_engine
  touch /workspace/.libs-installed
fi

# 6. Create a dev site if not present
if ! bench --site erpnext.localhost list-apps >/dev/null 2>&1; then
  echo "==> Creating dev site erpnext.localhost"
  bench new-site erpnext.localhost --mariadb-root-password 123 --admin-password admin --no-mariadb-socket
  bench --site erpnext.localhost install-app erpnext hrms frappe_armenia frappe_uae frappe_ai_local
fi

echo "==> bench ready at /workspace/frappe-bench"
bench --site erpnext.localhost list-apps
