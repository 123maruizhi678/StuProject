"""Backend-only Dify console access; never print or persist console credentials."""
import base64
import json
import os
import subprocess

import httpx


class DifyConsole:
    def __init__(self, base="http://127.0.0.1", container=None):
        self.http = httpx.Client(base_url=base.rstrip("/") + "/console/api/", timeout=60, trust_env=False)
        if container:
            # Explicit local-administrator bootstrap, scoped to the existing sole owner.
            code = '''
import json
from app import app
from extensions.ext_database import db
from models import Account, TenantAccountJoin
from services.account_service import AccountService
from libs.token import generate_csrf_token
with app.app_context():
    owners = db.session.query(Account).join(TenantAccountJoin, Account.id == TenantAccountJoin.account_id).filter(TenantAccountJoin.role == 'owner', Account.status == 'active').all()
    if len(owners) != 1:
        raise RuntimeError('Expected exactly one active local workspace owner')
    owner = owners[0]
    print('CUSTOMER_AUTH=' + json.dumps({'token': AccountService.get_account_jwt_token(owner), 'csrf': generate_csrf_token(owner.id)}))
'''
            proc = subprocess.run(["docker", "exec", "-i", container, "/app/api/.venv/bin/python", "-"], input=code, capture_output=True, text=True, encoding="utf-8", timeout=90)
            line = next((s for s in proc.stdout.splitlines() if s.startswith("CUSTOMER_AUTH=")), None)
            if proc.returncode or not line:
                raise RuntimeError("Local Dify owner session bootstrap failed; credentials were not logged")
            auth = json.loads(line.split("=", 1)[1])
            self.http.headers["Authorization"] = "Bearer " + auth["token"]
            csrf = auth["csrf"]
            self.http.cookies.set("csrf_token", csrf)
        else:
            email = os.environ["DIFY_CONSOLE_EMAIL"]
            password = base64.b64encode(os.environ["DIFY_CONSOLE_PASSWORD"].encode()).decode()
            response = self.http.post("login", json={"email": email, "password": password})
            response.raise_for_status()
            csrf = self.http.cookies.get("csrf_token")
        if not csrf:
            raise RuntimeError("Dify session has no CSRF token")
        self.http.headers["X-CSRF-Token"] = csrf

    def request(self, method, path, **kwargs):
        response = self.http.request(method, path, **kwargs)
        if response.is_error:
            # Avoid reflecting provider tokens or user input in errors.
            raise RuntimeError(f"Dify {method} {path}: HTTP {response.status_code}")
        return response.json()

    def apps(self):
        return self.request("GET", "apps", params={"page": 1, "limit": 100})["data"]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-container", default=None)
    args = parser.parse_args()
    console = DifyConsole(container=args.local_container)
    for app in console.apps():
        print(json.dumps({k: app.get(k) for k in ("id", "name", "mode")}, ensure_ascii=False))
        if app["mode"] == "workflow":
            draft = console.request("GET", f"apps/{app['id']}/workflows/draft")
            for node in draft.get("graph", {}).get("nodes", []):
                data = node.get("data", {})
                if data.get("type") == "llm":
                    print(json.dumps({"model": data.get("model")}, ensure_ascii=False))
