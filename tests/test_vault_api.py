"""End-to-end API behaviour for the credentials vault."""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_server
import vault as vault_module
from api_server import app
from main import SSHManager

client = TestClient(app)

PASSCODE = "a good long passcode"

HOSTS = {
    "hosts": [
        {"name": "prod-web", "hostname": "web.example.com", "username": "admin",
         "port": 22, "credential": "prod-admin", "group": "Production"},
        {"name": "dev-box", "hostname": "dev.example.com", "username": "dev",
         "port": 22, "credential": "prod-admin"},
        {"name": "no-creds", "hostname": "other.example.com", "username": "root", "port": 22},
    ]
}


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    """A real vault and host config, wired into the running app."""
    monkeypatch.setattr(api_server, "vault", vault_module.Vault(tmp_path / "vault.json"))
    monkeypatch.setattr(api_server, "vault_sessions", vault_module.VaultSessions())

    config = tmp_path / "hosts.json"
    config.write_text(json.dumps(HOSTS))

    manager = SSHManager(str(config))
    monkeypatch.setattr(api_server.api_manager, "ssh_manager", manager)
    api_server.api_manager.refresh_hosts_data()
    return tmp_path


def unlock(passcode=PASSCODE):
    response = client.post("/api/vault/unlock", json={"passcode": passcode})
    assert response.status_code == 200, response.text
    return {"X-Vault-Token": response.json()["token"]}


def create_vault(passcode=PASSCODE):
    response = client.post("/api/vault/create", json={"passcode": passcode})
    assert response.status_code == 200, response.text
    return {"X-Vault-Token": response.json()["token"]}, response.json()


# --- lifecycle ---------------------------------------------------------------

def test_status_before_the_vault_exists(vault_env):
    body = client.get("/api/vault/status").json()

    assert body["exists"] is False
    assert body["unlocked"] is False


def test_create_unlock_and_lock(vault_env):
    headers, body = create_vault()
    assert body["success"] is True
    assert "migration" not in body, "nothing is imported from the old setup"

    # The token from create is immediately usable
    assert client.get("/api/vault/credentials", headers=headers).status_code == 200
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is True

    client.post("/api/vault/lock", headers=headers)
    assert client.get("/api/vault/status", headers=headers).json()["unlocked"] is False
    assert client.get("/api/vault/credentials", headers=headers).status_code == 401


def test_a_fresh_page_starts_locked(vault_env):
    create_vault()

    # No token = a page that just loaded
    body = client.get("/api/vault/status").json()
    assert body["exists"] is True
    assert body["unlocked"] is False

    response = client.get("/api/vault/credentials")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "vault_locked"


def test_unlock_with_the_wrong_passcode(vault_env):
    create_vault()

    response = client.post("/api/vault/unlock", json={"passcode": "nope"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "bad_passcode"


def test_operations_before_the_vault_exists(vault_env):
    response = client.get("/api/vault/credentials")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "vault_missing"


def test_changing_the_passcode_relocks_other_pages(vault_env):
    headers, _ = create_vault()
    other_page = unlock()

    response = client.post("/api/vault/passcode", json={
        "current_passcode": PASSCODE, "new_passcode": "a different passcode",
    })

    assert response.status_code == 200
    assert client.get("/api/vault/credentials", headers=other_page).status_code == 401
    assert client.get("/api/vault/credentials", headers=headers).status_code == 401

    new_headers = unlock("a different passcode")
    assert client.get("/api/vault/credentials", headers=new_headers).status_code == 200


# --- credential CRUD ---------------------------------------------------------

def test_credential_crud(vault_env):
    headers, _ = create_vault()

    created = client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret", "description": "prod",
    })
    assert created.status_code == 200
    assert "password" not in created.json()["credential"], "listing payloads never carry secrets"

    listed = client.get("/api/vault/credentials", headers=headers).json()["credentials"]
    assert [c["name"] for c in listed] == ["prod-admin"]
    # Host associations come back with the listing
    assert sorted(listed[0]["used_by"]) == ["dev-box", "prod-web"]

    # The single-credential fetch is what the edit form uses, so it has the secret
    full = client.get("/api/vault/credentials/prod-admin", headers=headers).json()["credential"]
    assert full["password"] == "s3cret"

    updated = client.put("/api/vault/credentials/prod-admin", headers=headers, json={
        "name": "prod-admin", "type": "password", "description": "updated",
    })
    assert updated.status_code == 200
    # Omitting the password keeps the stored one
    assert client.get("/api/vault/credentials/prod-admin", headers=headers).json()["credential"]["password"] == "s3cret"


def test_duplicate_names_are_reported_for_the_ui_to_offer_a_choice(vault_env):
    headers, _ = create_vault()
    payload = {"name": "dupe", "type": "password", "password": "pw"}
    client.post("/api/vault/credentials", headers=headers, json=payload)

    response = client.post("/api/vault/credentials", headers=headers,
                           json={**payload, "name": "DUPE"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "duplicate_name"
    assert detail["name"] == "dupe"


def test_renaming_a_credential_updates_host_associations(vault_env, tmp_path):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "pw",
    })

    response = client.put("/api/vault/credentials/prod-admin", headers=headers, json={
        "name": "prod-root", "type": "password",
    })

    assert response.status_code == 200
    assert response.json()["renamed_hosts"] == 2

    hosts = {h["name"]: h for h in json.loads((tmp_path / "hosts.json").read_text())["hosts"]}
    assert hosts["prod-web"]["credential"] == "prod-root"
    assert hosts["dev-box"]["credential"] == "prod-root"
    # A host with no credential is left alone (startup gives it an empty one)
    assert hosts["no-creds"]["credential"] == ""


def test_deleting_a_credential_in_use_is_refused_and_names_the_hosts(vault_env):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "pw",
    })

    response = client.delete("/api/vault/credentials/prod-admin", headers=headers)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "credential_in_use"
    assert detail["count"] == 2
    assert sorted(detail["hosts"]) == ["dev-box", "prod-web"]

    # Still there
    assert client.get("/api/vault/credentials/prod-admin", headers=headers).status_code == 200


def test_deleting_an_unused_credential(vault_env):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "spare", "type": "key", "ssh_key_path": "~/.ssh/id_rsa",
    })

    response = client.delete("/api/vault/credentials/spare", headers=headers)

    assert response.status_code == 200
    assert client.get("/api/vault/credentials", headers=headers).json()["credentials"] == []


def test_every_credential_route_needs_an_unlocked_vault(vault_env):
    create_vault()

    assert client.get("/api/vault/credentials").status_code == 401
    assert client.get("/api/vault/credentials/x").status_code == 401
    assert client.post("/api/vault/credentials", json={
        "name": "x", "type": "password", "password": "p"}).status_code == 401
    assert client.put("/api/vault/credentials/x", json={
        "name": "x", "type": "password"}).status_code == 401
    assert client.delete("/api/vault/credentials/x").status_code == 401


# --- connecting --------------------------------------------------------------

def test_connecting_needs_the_vault_unlocked(vault_env):
    create_vault()

    response = client.post("/api/connect", json={"host_name": "prod-web"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "vault_locked"


def test_connecting_resolves_the_credential_from_the_vault(vault_env, monkeypatch):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret",
    })

    launched = {}
    monkeypatch.setattr(api_server.api_manager.ssh_manager, "launch_session",
                        lambda host, credential=None: launched.update(host=host, credential=credential))

    response = client.post("/api/connect", headers=headers, json={"host_name": "prod-web"})

    assert response.status_code == 200
    assert launched["credential"]["password"] == "s3cret"
    assert launched["host"]["name"] == "prod-web"


def test_connecting_passes_the_terminals_advice_back_to_the_ui(vault_env, monkeypatch):
    """The session is already up - these drive the toast, not the outcome."""
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret",
    })

    notice = {"kind": "warning", "text": "Opened in a new macOS Terminal window - Accessibility"}
    monkeypatch.setattr(api_server.api_manager.ssh_manager, "launch_session",
                        lambda host, credential=None: {
                            "terminal": "terminal", "terminal_name": "macOS Terminal",
                            "session_id": "/dev/ttys003", "notices": [notice],
                        })

    body = client.post("/api/connect", headers=headers, json={"host_name": "prod-web"}).json()

    assert body["terminal"] == "terminal"
    assert body["terminal_name"] == "macOS Terminal"
    assert body["notices"] == [notice]


def test_connecting_survives_a_launcher_that_reports_nothing(vault_env, monkeypatch):
    """Older/stubbed launchers return None - the connect must still succeed."""
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret",
    })
    monkeypatch.setattr(api_server.api_manager.ssh_manager, "launch_session",
                        lambda host, credential=None: None)

    body = client.post("/api/connect", headers=headers, json={"host_name": "prod-web"}).json()

    assert body["success"] is True
    assert body["notices"] == []


def test_connecting_a_host_without_a_credential_explains_itself(vault_env):
    headers, _ = create_vault()

    response = client.post("/api/connect", headers=headers, json={"host_name": "prod-web"})

    assert response.status_code == 400
    assert "not in the vault" in response.json()["detail"]


# --- the username a credential carries ---------------------------------------

def test_a_credentials_username_overrides_the_hosts(vault_env, monkeypatch):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret", "username": "ubuntu",
    })

    # It travels with the listing, so the tiles can show the real login
    listed = client.get("/api/vault/credentials", headers=headers).json()["credentials"]
    assert listed[0]["username"] == "ubuntu"

    launched = {}
    monkeypatch.setattr(api_server.api_manager.ssh_manager, "launch_session",
                        lambda host, credential=None: launched.update(host=host, credential=credential))

    # prod-web says "admin", the credential says "ubuntu" - the credential wins
    assert client.post("/api/connect", headers=headers,
                       json={"host_name": "prod-web"}).status_code == 200
    assert api_server.ssh_session.effective_username(
        launched["host"], launched["credential"]) == "ubuntu"


def test_a_host_can_leave_the_username_to_its_credential(vault_env, monkeypatch):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret", "username": "ubuntu",
    })

    created = client.post("/api/hosts", json={
        "name": "no-user", "hostname": "srv.example.com", "credential": "prod-admin",
    })
    assert created.status_code == 200, created.text
    assert created.json()["host"]["username"] == ""

    launched = {}
    monkeypatch.setattr(api_server.api_manager.ssh_manager, "launch_session",
                        lambda host, credential=None: launched.update(host=host, credential=credential))

    assert client.post("/api/connect", headers=headers,
                       json={"host_name": "no-user"}).status_code == 200
    assert api_server.ssh_session.effective_username(
        launched["host"], launched["credential"]) == "ubuntu"


def test_connecting_with_no_username_anywhere_is_refused(vault_env):
    headers, _ = create_vault()
    client.post("/api/vault/credentials", headers=headers, json={
        "name": "prod-admin", "type": "password", "password": "s3cret",
    })
    client.post("/api/hosts", json={
        "name": "no-user", "hostname": "srv.example.com", "credential": "prod-admin",
    })

    response = client.post("/api/connect", headers=headers, json={"host_name": "no-user"})

    assert response.status_code == 400
    assert "no username" in response.json()["detail"]
