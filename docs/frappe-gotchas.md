# Frappe Custom App Gotchas (the hard-won lessons)

This is a living document of every non-obvious thing we hit while building
`frappe_armenia` / `frappe_uae` / `frappe_ai_local`. **If you are an AI agent
adding a new app, read this first.**

## 1. `modules.txt` must contain a sub-module name, NOT the app name

**The bug:** `frappe/__init__.py:1432` defines:

```python
def get_module_path(module, *joins):
    from frappe.modules.utils import get_module_app
    app = get_module_app(module)
    return get_pymodule_path(app + "." + scrub(module), *joins)
```

This concatenates `app + "." + scrub(module)`. If `module == app` (e.g. you
put `frappe_armenia` as the entry in `modules.txt`), Python tries to import
`frappe_armenia.frappe_armenia` — which is not a real module, and the install
fails with `ModuleNotFoundError: No module named 'frappe_armenia.frappe_armenia'`.

**The fix:** the first line of `apps/<your_app>/<your_app>/modules.txt` must be
the name of a **sub-directory** under the app — not the app name itself. So:

```
# apps/frappe_armenia/frappe_armenia/modules.txt
armenia
```

Plus you must have the corresponding sub-directory:

```
apps/frappe_armenia/frappe_armenia/armenia/__init__.py
```

This is the same convention Frappe and ERPNext use:
- `apps/erpnext/erpnext/modules.txt` → `Accounts`, `CRM`, `Buying`, …
- `apps/erpnext/erpnext/accounts/__init__.py` exists for each

**For our 3 apps, the convention we use:**

| App | modules.txt | sub-dir created |
|---|---|---|
| `frappe_armenia` | `armenia` | `apps/frappe_armenia/frappe_armenia/armenia/` |
| `frappe_uae` | `uae` | `apps/frappe_uae/frappe_uae/uae/` |
| `frappe_ai_local` | `ai_local` | `apps/frappe_ai_local/frappe_ai_local/ai_local/` |

## 2. `setuptools<70` is required (Frappe v15 still uses `pkg_resources`)

The `setuptools>=70` release removed `pkg_resources`. Frappe v15 has code that
still does `import pkg_resources`. Pin to:

```toml
# In the bench container, after pip install
pip install 'setuptools<70'
```

Symptom: `ModuleNotFoundError: No module named 'pkg_resources'`

## 3. MariaDB needs `character_set_server=utf8mb4` to create sites

`frappe/database/mariadb/setup_db.py:6` enforces:

```python
REQUIRED_MARIADB_CONFIG = {
    "character_set_server": "utf8mb4",
    "collation_server": "utf8mb4_unicode_ci",
}
```

Add to `mariadb.conf.d/50-server.cnf`:

```ini
[client]
default-character-set = utf8mb4

[mysqld]
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
innodb-file-format = barracuda
innodb-file-per-table = 1
innodb-large-prefix = 1
```

Then `docker restart compose-mariadb-1`.

## 4. `bench get-app` validates the GitHub org for non-frappe apps

`bench/utils/__init__.py:469` calls `find_org(app_name)` which does a real
GitHub API lookup against `frappe` and `erpnext` orgs. For our apps the
check fails with `InvalidRemoteException: <app> not found under frappe or
erpnext GitHub accounts`.

**Fix:** push the app to its own GitHub repo first (e.g.
`armosphera/frappe_armenia`), then `bench get-app armosphera/frappe_armenia
--branch main`. The check is satisfied if the org matches *any* GitHub
account. (Our apps are at `armosphera/frappe_armenia`, `armosphera/frappe_uae`,
`armosphera/frappe_ai_local`.)

## 5. `apps.txt` must list every app in dependency order

After `bench get-app`, verify the contents of `frappe-bench/sites/apps.txt`:

```
frappe
erpnext
hrms
frappe_armenia
frappe_uae
frappe_ai_local
```

If a line is malformed (e.g. `erpnextfrappe_armenia` from a failed get-app),
`get_all_apps()` returns that garbage and the install fails with the same
ModuleNotFoundError pattern as #1.

## 6. `frappe-bench` must be a *bind mount*, not a *named volume*

Using `bench-data:/workspace/frappe-bench` in compose creates a *named volume*
that shadows the host directory. When the container is recreated, the volume
keeps the old state. Use a bind mount instead:

```yaml
volumes:
  - ${REPO_ROOT}:/workspace
```

And let the `frappe-bench/` subdir be created by `bench init` at runtime.

## 7. `bench set-config` without `-g` tries to literal_eval the value

`bench set-config` with a single arg is site-scoped (writes to
`sites/<site>/site_config.json`). For global config (the bench dir), use
`-g`. Without `-g`, `set-config db_host mariadb` fails with
`ValueError: malformed node or string on line 1: <ast.Name object at ...>`.

## 8. The bench container must have a real Redis server, not just `redis-cli`

Frappe's `bench init` runs `redis-server --version` to detect the local Redis
version. The `redis-tools` apt package only ships the client. Install both:

```dockerfile
RUN apt-get install -y redis-server redis-tools
```

## 9. The bench container must have `mariadb-server`, not just `mariadb-client`

`bench init` calls `mysql --version` and may run local mariadb checks
during config generation. Install both.

## 10. The bench container must have a current `yarn` (1.x)

Debian's `yarn` is 0.32 (a 2017 relic). Modern Frappe needs yarn 1.22+ for
`yarn install --check-files`. Install from yarnpkg's repo:

```dockerfile
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor -o /usr/share/keyrings/yarn-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/yarn-archive-keyring.gpg] https://dl.yarnpkg.com/debian/ stable main" \
       > /etc/apt/sources.list.d/yarn.list \
    && apt-get update && apt-get install -y yarn
```

## 11. The bench container must have `cron` installed

Frappe's `bench init` uses `crontab` to inspect the system crontab. Without
`cron` apt package, you get `FileNotFoundError: '/usr/bin/crontab'`.

## 12. `wkhtmltopdf` is NOT in Debian's apt repo (slim or bookworm)

It's not in the default repo. Two options:
- Use the official `frappe/erpnext-docker` image which has it
- Add the wkhtmltopdf apt repo manually
- Skip it in dev (only needed for print-to-PDF in production)

## 13. `sites/<site>/apps.txt` is NOT auto-created

After `bench new-site`, the site dir has `site_config.json` but no `apps.txt`.
The site-level `apps.txt` is the list of apps that **site** says are installed;
Frappe's `setup_module_map` reads from it. If you add apps later via
`bench --site <site> install-app <app>`, the bench *does* update this file,
but the `frappe get_apps()` only sees what's in `sites/apps.txt` (the bench
dir level). Keep both in sync.

## 14. Newer Python `setuptools` removes `pkg_resources` (repeat of #2)

Already covered. Just a reminder.

---

**If you hit a ModuleNotFoundError with the form
`<app>.<sub>` where `<sub>` equals `<app>`, it's always #1.**
