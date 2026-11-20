#!/usr/bin/env python3
"""Deploy the New Year's Eve taxi dashboard to the kit's built-in Dash Server.

Reads every file in this folder (minus README and install scripts) and uploads them as a hosted Dash app
called "nye-taxis", bound to the starter-kit profile. Then promotes the revision to live. No credentials
in the payload: Dash Server supplies them through the profile at runtime.

Idempotent: on a second run, it updates the existing app and redeploys instead of creating a duplicate.

Environment overrides:
    APP_NAME             hosted-app name (default: nye-taxis)
    DASH_SERVER_URL      base URL (default: discovered from `exakit status --json`, then 127.0.0.1:5100)
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
APP_NAME = os.environ.get("APP_NAME", "nye-taxis")
SKIP_NAMES = {"README.md", "install.sh", "install.py", ".gitignore"}


def dash_server_url():
    if u := os.environ.get("DASH_SERVER_URL"):
        return u.rstrip("/")
    try:
        out = subprocess.check_output(["exakit", "status", "--json"], text=True, timeout=10)
        url = (json.loads(out).get("urls") or {}).get("dash-server")
        if url:
            return url.rstrip("/")
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return "http://127.0.0.1:5100"


def ensure_geojson():
    """taxi_zones.geojson must sit next to app.py for Dash Server to upload it. In the repo it lives
    under content/datasets/nyc_taxi_zones/; in the zip bundle it is already here."""
    target = HERE / "taxi_zones.geojson"
    if target.exists():
        return
    repo_copy = HERE.parents[4] / "datasets" / "nyc_taxi_zones" / "taxi_zones.geojson"
    if repo_copy.exists():
        target.write_text(repo_copy.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copied {repo_copy} -> taxi_zones.geojson")
        return
    sys.exit(f"taxi_zones.geojson not found next to {__file__}; see README.md.")


def collect_files():
    out = []
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or p.name in SKIP_NAMES:
            continue
        out.append({"path": p.relative_to(HERE).as_posix(),
                    "content": p.read_text(encoding="utf-8")})
    return out


def mcp_call(url, name, arguments):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    req = urllib.request.Request(
        f"{url}/mcp",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read().decode("utf-8")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach Dash Server at {url}: {e}. Is it running? (exakit start dash-server)")
    try:
        resp = json.loads(body)
    except json.JSONDecodeError:
        last = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")][-1]
        resp = json.loads(last)
    if "error" in resp:
        sys.exit(f"{name}: {resp['error']}")
    result = resp.get("result") or {}
    if result.get("isError"):
        text = (result.get("content") or [{}])[0].get("text", "unknown error")
        sys.exit(f"{name} failed:\n{text}")
    return result.get("structuredContent") or {}


def existing_app(url, name):
    apps = mcp_call(url, "apps_list", {}).get("apps") or []
    return any(a.get("name") == name for a in apps)


def main():
    url = dash_server_url()
    ensure_geojson()
    files = collect_files()
    sizes = sum(len(f["content"]) for f in files)
    print(f"Target: {url}    App: {APP_NAME}    Files: {len(files)} ({sizes:,} bytes)")

    if existing_app(url, APP_NAME):
        print(f"App {APP_NAME} exists - updating files.")
        mcp_call(url, "app_put_files", {"name": APP_NAME, "files": files})
    else:
        print(f"Creating app {APP_NAME} ...")
        mcp_call(url, "app_create_from_files", {
            "name": APP_NAME,
            "template": "exasol-analytics",
            "files": files,
            "start_immediately": False,
        })

    print("Deploying live ...")
    mcp_call(url, "app_deploy_draft", {
        "name": APP_NAME,
        "deployment_target": "live",
        "auto_rollback_on_health_failure": True,
    })
    print(f"\nDashboard: {url}/apps/{APP_NAME}")


if __name__ == "__main__":
    main()
