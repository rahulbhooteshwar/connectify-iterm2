#!/usr/bin/env python3
"""
FastAPI Server for SSH Session Manager
Modern web API to replace Gradio interface
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import threading
import time
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import uvicorn

import iterm_profiles
import vault as vault_module
from main import (
    DEFAULT_HOST_THEME,
    SSHManager,
    group_hosts,
    normalize_group,
    normalize_theme,
)


class HostModel(BaseModel):
    name: str
    hostname: str
    username: str
    port: int = 22
    auth_method: str = "password"
    ssh_key_path: Optional[str] = None
    iterm_profile: str = "Default"
    # Name of the vault credential used to authenticate (empty = none yet)
    credential: str = ""
    # Optional grouping label used to organize the host list. Empty means the
    # host is rendered ungrouped.
    group: str = ""
    # Tile theme in the web UI: default (neutral), red, green or orange.
    theme: str = DEFAULT_HOST_THEME
    tags: List[str] = []
    # SSH "-o" options (e.g. "PreferredAuthentications=password"). None means
    # "not configured" so the backend applies auth-method defaults; an empty
    # list means "no extra options".
    ssh_options: Optional[List[str]] = None

    @field_validator('group')
    @classmethod
    def _clean_group(cls, value):
        return normalize_group(value)

    @field_validator('theme')
    @classmethod
    def _clean_theme(cls, value):
        return normalize_theme(value)


class HostCreate(HostModel):
    pass


class HostUpdate(HostModel):
    pass


class ConnectRequest(BaseModel):
    host_name: str


class VaultPasscodeRequest(BaseModel):
    passcode: str


class VaultChangePasscodeRequest(BaseModel):
    current_passcode: str
    new_passcode: str


class CredentialRequest(BaseModel):
    name: str
    type: str
    description: str = ""
    # Only one of these applies, depending on `type`
    password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    passphrase: Optional[str] = None


class SearchRequest(BaseModel):
    search_term: str = ""
    tag_filter: str = ""


class ImportRequest(BaseModel):
    hosts: List[HostCreate]


class APISSHManager:
    def __init__(self, config_file="~/.connectify/hosts.json"):
        self.ssh_manager = SSHManager(config_file)
        self.all_hosts = []
        self.refresh_hosts_data()

    def refresh_hosts_data(self):
        """Refresh the hosts data from config"""
        self.all_hosts = self.ssh_manager.config.get('hosts', [])

    def get_hosts_data(self, search_term="", tag_filter=""):
        """Get hosts data filtered by search term or tag"""
        if tag_filter and tag_filter != "All Tags":
            hosts = [host for host in self.all_hosts if tag_filter in host.get('tags', [])]
        elif search_term.strip():
            hosts = self.ssh_manager.filter_hosts(search_term)
        else:
            hosts = self.all_hosts
        return hosts

    def get_unique_groups(self):
        """Get all group names currently in use, for the group picker"""
        groups = {normalize_group(host.get('group')) for host in self.all_hosts}
        groups.discard('')
        return sorted(groups, key=str.lower)

    def get_unique_tags(self):
        """Get all unique tags from hosts"""
        tags = set()
        for host in self.all_hosts:
            host_tags = host.get('tags', [])
            tags.update(host_tags)
        return sorted(list(tags))

    def get_available_profiles(self):
        """Get every iTerm2 profile that can be assigned to a host"""
        host_profiles = [
            host.get('iterm_profile')
            for host in self.all_hosts
            if host.get('iterm_profile')
        ]
        return iterm_profiles.list_available_profiles(extra_names=host_profiles)

    def get_hosts_by_groups(self, search_term="", tag_filter=""):
        """Get hosts organized by their configured group.

        Hosts without a group come back separately so the UI can render them
        as-is instead of inventing a bucket for them.
        """
        hosts = self.get_hosts_data(search_term, tag_filter)
        groups, ungrouped_hosts = group_hosts(hosts)

        return {
            "groups": groups,
            "ungrouped_hosts": ungrouped_hosts,
            "total_hosts": len(hosts)
        }

    def connect_to_host(self, host_name: str, vault_key=None):
        """Launch a session, resolving the host's credential from the vault"""
        host = next((h for h in self.all_hosts if h['name'] == host_name), None)

        if not host:
            raise HTTPException(status_code=404, detail=f"Host '{host_name}' not found")

        credential_name = (host.get('credential') or '').strip()
        credential = None

        if credential_name:
            if vault_key is None:
                raise vault_locked_error()
            try:
                credential = vault.get_credential(vault_key, credential_name)
            except vault_module.CredentialNotFound:
                raise HTTPException(
                    status_code=400,
                    detail=f"Credential '{credential_name}' for '{host['name']}' is not in the vault. "
                           f"Assign a credential to this host."
                )
        elif host.get('auth_method') == 'password' or host.get('ssh_key_path'):
            # Pre-vault host that was never migrated
            raise HTTPException(
                status_code=400,
                detail=f"'{host['name']}' has no credential yet. Edit the host and pick one from the vault."
            )

        try:
            # Launch the SSH session in a separate thread
            def launch_session():
                try:
                    self.ssh_manager.launch_iterm_session(host, credential)
                except Exception as e:
                    logging.error(f"Error launching session for {host_name}: {e}")
                    print(f"❌ Error launching session for {host_name}: {e}")

            thread = threading.Thread(target=launch_session, daemon=True)
            thread.start()

            return {
                "success": True,
                "message": f"SSH session launched for {host['name']}",
                "host": host
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")

    def add_host(self, host_data: dict):
        """Add a new host"""
        self.ssh_manager.add_host_programmatic(host_data)
        self.refresh_hosts_data()
        return self.ssh_manager.get_host(host_data['name'])

    def update_host(self, original_name: str, host_data: dict):
        """Update an existing host"""
        self.ssh_manager.update_host(original_name, host_data)
        self.refresh_hosts_data()
        return self.ssh_manager.get_host(host_data['name'])

    def delete_host(self, host_name: str):
        """Delete a host"""
        self.ssh_manager.delete_host(host_name)
        self.refresh_hosts_data()
        return True

# The encrypted credentials vault and the in-memory unlocked sessions.
# Sessions live only in this process, so reloading the page re-locks the vault.
vault = vault_module.Vault()
vault_sessions = vault_module.VaultSessions()


def vault_locked_error():
    """401 that the UI recognises and answers with the unlock dialog"""
    return HTTPException(
        status_code=401,
        detail={"code": "vault_locked", "message": "The vault is locked"},
    )


def get_vault_key(x_vault_token: Optional[str] = Header(None)):
    """Resolve an unlock token to its derived key, or fail with 401"""
    if not vault.exists():
        raise HTTPException(
            status_code=409,
            detail={"code": "vault_missing", "message": "The vault has not been created yet"},
        )
    key = vault_sessions.get_key(x_vault_token)
    if key is None:
        raise vault_locked_error()
    return key


def optional_vault_key(x_vault_token: Optional[str] = Header(None)):
    """Same, but returns None instead of failing (for endpoints that adapt)"""
    return vault_sessions.get_key(x_vault_token)


# Initialize the API manager
api_manager = APISSHManager()

# Create FastAPI app
app = FastAPI(
    title="SSH Session Manager API",
    description="Modern web API for managing SSH sessions with iTerm2",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (will be created)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Cache for static file content and existence check
_static_file_cache = {
    'html_content': None,
    'html_exists': None,
    'last_check': 0,
    'cache_duration': 300  # 5 minutes cache
}

def get_cached_html_content():
    """Get HTML content with caching to avoid repeated file system calls"""
    current_time = time.time()
    cache = _static_file_cache

    # Check if cache is still valid (within cache duration)
    if (cache['html_content'] is not None and
        cache['last_check'] > 0 and
        (current_time - cache['last_check']) < cache['cache_duration']):
        return cache['html_content'], cache['html_exists']

    # Cache expired or not initialized, refresh it
    try:
        html_file = static_dir / "index.html"

        # Use absolute path to avoid working directory issues
        html_file_abs = html_file.resolve()

        if html_file_abs.exists() and html_file_abs.is_file():
            # Read the file content once and cache it
            try:
                with open(html_file_abs, 'r', encoding='utf-8') as f:
                    content = f.read()
                cache['html_content'] = content
                cache['html_exists'] = True
                logging.info(f"Cached HTML content from {html_file_abs}")
            except Exception as e:
                logging.error(f"Error reading HTML file {html_file_abs}: {e}")
                cache['html_content'] = None
                cache['html_exists'] = False
        else:
            cache['html_content'] = None
            cache['html_exists'] = False
            logging.warning(f"HTML file not found at {html_file_abs}")

    except Exception as e:
        logging.error(f"Error checking HTML file existence: {e}")
        cache['html_content'] = None
        cache['html_exists'] = False

    # Update cache timestamp
    cache['last_check'] = current_time

    return cache['html_content'], cache['html_exists']


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML page with caching to prevent file system issues"""
    try:
        html_content, html_exists = get_cached_html_content()

        if html_exists and html_content:
            # Return cached HTML content directly
            return HTMLResponse(content=html_content, media_type="text/html")
        else:
            # Return fallback HTML if static files don't exist
            logging.warning("Serving fallback HTML - static files not found")
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SSH Session Manager</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { 
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        max-width: 800px; 
                        margin: 50px auto; 
                        padding: 20px;
                        background: #f5f5f5;
                        color: #333;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        text-align: center;
                    }
                    .error-icon { font-size: 4rem; color: #e74c3c; margin-bottom: 20px; }
                    h1 { color: #2c3e50; margin-bottom: 10px; }
                    .error-message { color: #7f8c8d; margin-bottom: 30px; }
                    .retry-btn {
                        background: #3498db;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 5px;
                        cursor: pointer;
                        font-size: 16px;
                        text-decoration: none;
                        display: inline-block;
                    }
                    .retry-btn:hover { background: #2980b9; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">⚠️</div>
                    <h1>SSH Session Manager</h1>
                    <p class="error-message">Static files not found. Please ensure the UI is built properly.</p>
                    <a href="/" class="retry-btn">🔄 Retry</a>
                    <br><br>
                    <small>If this issue persists after 24+ hours of running, please restart the server.</small>
                </div>
            </body>
            </html>
            """)

    except Exception as e:
        logging.error(f"Error in serve_frontend: {e}")
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SSH Session Manager - Error</title>
        </head>
        <body>
            <h1>SSH Session Manager</h1>
            <p>Server error occurred. Please restart the application.</p>
        </body>
        </html>
        """, status_code=500)


@app.get("/api/hosts")
async def get_hosts(search_term: str = "", tag_filter: str = ""):
    """Get all hosts with optional filtering"""
    try:
        api_manager.refresh_hosts_data()
        result = api_manager.get_hosts_by_groups(search_term, tag_filter)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tags")
async def get_tags():
    """Get all unique tags"""
    try:
        api_manager.refresh_hosts_data()
        tags = api_manager.get_unique_tags()
        return {
            "success": True,
            "tags": tags
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vault/status")
async def vault_status(x_vault_token: Optional[str] = Header(None)):
    """Whether the vault exists and whether this page has it unlocked"""
    unlocked = vault_sessions.get_key(x_vault_token) is not None
    return {
        "success": True,
        "exists": vault.exists(),
        "unlocked": unlocked,
        "path": str(vault.path),
    }


@app.post("/api/vault/create")
async def vault_create(request: VaultPasscodeRequest):
    """Create the vault, migrating any pre-vault credentials into it"""
    try:
        credentials, assignments, summary = api_manager.ssh_manager.build_legacy_credentials()
        key = vault.create(request.passcode, credentials)
        migrated_hosts = api_manager.ssh_manager.apply_credential_assignments(assignments)
        api_manager.refresh_hosts_data()

        return {
            "success": True,
            "token": vault_sessions.create(key),
            "migration": {
                "credentials": len(credentials),
                "hosts": migrated_hosts,
                "passwords": summary['passwords'],
                "keys": summary['keys'],
                "skipped": summary['skipped'],
            },
        }
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/vault/unlock")
async def vault_unlock(request: VaultPasscodeRequest):
    """Unlock the vault for this page; the key never leaves the server"""
    try:
        key = vault.unlock(request.passcode)
    except vault_module.VaultNotInitialized:
        raise HTTPException(
            status_code=409,
            detail={"code": "vault_missing", "message": "The vault has not been created yet"},
        )
    except vault_module.InvalidPasscode:
        raise HTTPException(status_code=401, detail={"code": "bad_passcode", "message": "Incorrect passcode"})
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "token": vault_sessions.create(key)}


@app.post("/api/vault/lock")
async def vault_lock(x_vault_token: Optional[str] = Header(None)):
    """Forget this page's unlocked session"""
    vault_sessions.revoke(x_vault_token)
    return {"success": True, "message": "Vault locked"}


@app.post("/api/vault/passcode")
async def vault_change_passcode(request: VaultChangePasscodeRequest):
    """Re-encrypt the vault under a new passcode"""
    try:
        key = vault.change_passcode(request.current_passcode, request.new_passcode)
    except vault_module.InvalidPasscode:
        raise HTTPException(status_code=401, detail={"code": "bad_passcode", "message": "Incorrect passcode"})
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Every existing session was derived from the old passcode
    vault_sessions.revoke_all()
    return {"success": True, "token": vault_sessions.create(key)}


@app.get("/api/vault/credentials")
async def list_credentials(key=Depends(get_vault_key)):
    """Credential list, without any secrets, plus their host associations"""
    try:
        api_manager.refresh_hosts_data()
        credentials = [
            vault_module.public_credential(
                credential,
                used_by=api_manager.ssh_manager.hosts_using_credential(credential['name']),
            )
            for credential in vault.list_credentials(key)
        ]
        credentials.sort(key=lambda c: c['name'].lower())
        return {"success": True, "credentials": credentials}
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/vault/credentials/{name}")
async def get_credential(name: str, key=Depends(get_vault_key)):
    """Full credential including its secret, for the edit form"""
    try:
        return {"success": True, "credential": vault.get_credential(key, name)}
    except vault_module.CredentialNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/vault/credentials")
async def create_credential(request: CredentialRequest, key=Depends(get_vault_key)):
    """Add a credential, refusing duplicate names"""
    try:
        credential = vault.add_credential(key, request.dict())
        return {
            "success": True,
            "message": f"Credential '{credential['name']}' created",
            "credential": vault_module.public_credential(credential, used_by=[]),
        }
    except vault_module.DuplicateCredentialName as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate_name", "name": e.name, "message": str(e)},
        )
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/vault/credentials/{name}")
async def update_credential(name: str, request: CredentialRequest, key=Depends(get_vault_key)):
    """Update a credential; renaming follows through to every host using it"""
    try:
        credential, previous_name = vault.update_credential(key, name, request.dict())
    except vault_module.CredentialNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except vault_module.DuplicateCredentialName as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate_name", "name": e.name, "message": str(e)},
        )
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))

    renamed_hosts = api_manager.ssh_manager.rename_credential_references(
        previous_name, credential['name']
    )
    api_manager.refresh_hosts_data()

    message = f"Credential '{credential['name']}' updated"
    if renamed_hosts:
        message += f" ({renamed_hosts} host(s) updated)"

    return {
        "success": True,
        "message": message,
        "renamed_hosts": renamed_hosts,
        "credential": vault_module.public_credential(
            credential, used_by=api_manager.ssh_manager.hosts_using_credential(credential['name'])
        ),
    }


@app.delete("/api/vault/credentials/{name}")
async def delete_credential(name: str, key=Depends(get_vault_key)):
    """Delete a credential - refused while any host still uses it"""
    api_manager.refresh_hosts_data()
    used_by = api_manager.ssh_manager.hosts_using_credential(name)

    if used_by:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "credential_in_use",
                "name": name,
                "hosts": used_by,
                "count": len(used_by),
                "message": f"{len(used_by)} host(s) still use '{name}'",
            },
        )

    try:
        vault.delete_credential(key, name)
    except vault_module.CredentialNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except vault_module.VaultError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "message": f"Credential '{name}' deleted"}


@app.get("/api/groups")
async def get_groups():
    """Get all group names in use, so the form can offer them"""
    try:
        api_manager.refresh_hosts_data()
        return {
            "success": True,
            "groups": api_manager.get_unique_groups()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles")
async def get_profiles():
    """Get all iTerm2 profiles available for host configuration"""
    try:
        api_manager.refresh_hosts_data()
        profiles = api_manager.get_available_profiles()
        return {
            "success": True,
            "profiles": profiles,
            # Browser profiles are installed for the user but can't host an SSH
            # session, so they never appear in the selector.
            "bundled": [
                p["name"] for p in iterm_profiles.list_bundled_profiles()
                if not p.get("is_browser")
            ]
        }
    except Exception as e:
        logging.error(f"Error listing iTerm2 profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profiles/install")
async def install_profiles():
    """(Re)install the iTerm2 profiles shipped with Connectify"""
    try:
        result = iterm_profiles.install_bundled_profiles(force=True, quiet=True)
        changed = result["installed"] + result["updated"]
        return {
            "success": not result["errors"],
            "message": (
                f"Installed {len(changed)} profile(s) into iTerm2"
                if changed else "iTerm2 profiles are already up to date"
            ),
            "result": result
        }
    except Exception as e:
        logging.error(f"Error installing iTerm2 profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/connect")
async def connect_host(request: ConnectRequest, background_tasks: BackgroundTasks,
                       x_vault_token: Optional[str] = Header(None)):
    """Connect to a specific host, using its credential from the unlocked vault"""
    try:
        result = api_manager.connect_to_host(
            request.host_name, vault_sessions.get_key(x_vault_token)
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hosts")
async def create_host(host: HostCreate):
    """Create a new host"""
    try:
        result = api_manager.add_host(host.dict())
        return {
            "success": True,
            "message": f"Host '{host.name}' created successfully",
            "host": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/hosts/{host_name}")
async def update_host(host_name: str, host: HostUpdate):
    """Update an existing host"""
    try:
        result = api_manager.update_host(host_name, host.dict())
        return {
            "success": True,
            "message": f"Host '{host.name}' updated successfully",
            "host": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/hosts/{host_name}")
async def delete_host(host_name: str):
    """Delete a host"""
    try:
        api_manager.delete_host(host_name)
        return {
            "success": True,
            "message": f"Host '{host_name}' deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/hosts")
async def export_hosts():
    """Export current host configurations"""
    try:
        hosts = api_manager.all_hosts
        # Secrets live in the vault, never in an export - hosts only carry the
        # credential name
        export_data = [
            {k: v for k, v in host.items() if k != 'password'}
            for host in hosts
        ]
        
        return JSONResponse(
            content={"hosts": export_data},
            headers={
                "Content-Disposition": "attachment; filename=ssh_hosts_export.json"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/template")
async def export_template():
    """Export sample template"""
    template = {
        "hosts": [
            {
                "name": "Example Server",
                "hostname": "example.com",
                "username": "user",
                "port": 22,
                "credential": "prod-admin",
                "iterm_profile": "connectify-PROD",
                "group": "Production",
                "theme": "red",
                "tags": ["production", "web"],
                "ssh_options": ["PreferredAuthentications=password", "PubkeyAuthentication=no"]
            },
            {
                "name": "Dev Server",
                "hostname": "dev.example.com",
                "username": "developer",
                "port": 2222,
                "credential": "my-ssh-key",
                "iterm_profile": "connectify-NONPROD",
                "group": "Development",
                "theme": "green",
                "tags": ["development", "testing"],
                "ssh_options": ["PreferredAuthentications=publickey", "PasswordAuthentication=no"]
            }
        ],
        "_note": "'credential' is the name of a credential in the Connectify vault - "
                 "create it on the Vault page (secrets are never part of an import or "
                 "export). 'group' is optional; hosts without one are listed ungrouped. "
                 "'theme' is one of default, red, green, orange."
    }

    return JSONResponse(
        content=template,
        headers={
            "Content-Disposition": "attachment; filename=ssh_hosts_template.json"
        }
    )


@app.post("/api/import/hosts")
async def import_hosts(import_data: ImportRequest):
    """Import host configurations.

    Secrets are never imported - hosts reference a credential by name, and the
    credential itself is created on the Vault page.
    """
    try:
        imported_count = 0
        errors = []
        warnings = []

        known_credentials = set()
        for host in api_manager.all_hosts:
            if host.get('credential'):
                known_credentials.add(host['credential'].lower())

        for host_data in import_data.hosts:
            try:
                api_manager.add_host(host_data.dict())
                imported_count += 1

                credential = (host_data.credential or '').strip()
                if not credential:
                    warnings.append(
                        f"Host '{host_data.name}' has no credential - assign one before connecting."
                    )
                elif credential.lower() not in known_credentials:
                    warnings.append(
                        f"Host '{host_data.name}' references credential '{credential}'. "
                        f"Create it on the Vault page if it doesn't exist yet."
                    )
            except Exception as e:
                errors.append(f"Failed to import '{host_data.name}': {str(e)}")

        return {
            "success": True,
            "message": f"Imported {imported_count} host(s)" + (f" with {len(warnings)} warning(s)" if warnings else ""),
            "imported_count": imported_count,
            "errors": errors if errors else None,
            "warnings": warnings if warnings else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "success": True,
        "status": "healthy",
        "service": "SSH Session Manager API"
    }


@app.get("/api/config")
async def get_config():
    """Get configuration information"""
    try:
        api_manager.refresh_hosts_data()
        return {
            "success": True,
            "total_hosts": len(api_manager.all_hosts),
            "total_tags": len(api_manager.get_unique_tags()),
            "config_file": str(api_manager.ssh_manager.config_file)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh-cache")
async def refresh_static_cache():
    """Manually refresh the static file cache"""
    try:
        # Clear the cache to force a refresh
        _static_file_cache['html_content'] = None
        _static_file_cache['html_exists'] = None
        _static_file_cache['last_check'] = 0

        # Get fresh content
        html_content, html_exists = get_cached_html_content()

        return {
            "success": True,
            "message": "Static file cache refreshed",
            "html_exists": html_exists,
            "cache_timestamp": _static_file_cache['last_check']
        }
    except Exception as e:
        logging.error(f"Error refreshing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache refresh error: {str(e)}")


@app.get("/api/cache-status")
async def get_cache_status():
    """Get current cache status for debugging"""
    try:
        return {
            "success": True,
            "cache_info": {
                "html_exists": _static_file_cache['html_exists'],
                "html_content_length": len(_static_file_cache['html_content']) if _static_file_cache['html_content'] else 0,
                "last_check": _static_file_cache['last_check'],
                "cache_duration": _static_file_cache['cache_duration'],
                "cache_age_seconds": time.time() - _static_file_cache['last_check'] if _static_file_cache['last_check'] > 0 else -1,
                "static_dir": str(static_dir.resolve())
            }
        }
    except Exception as e:
        logging.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def launch_api_server(config_file="~/.connectify/hosts.json", port=7860, host="127.0.0.1", silent=False):
    """Launch the FastAPI server"""
    global api_manager

    # Configure logging
    log_level = logging.ERROR if silent else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler() if not silent else logging.NullHandler()
        ]
    )

    # Initialize API manager
    api_manager = APISSHManager(config_file)

    # Initialize the static file cache on startup
    try:
        html_content, html_exists = get_cached_html_content()
        if html_exists:
            logging.info("Static HTML file cached successfully on startup")
        else:
            logging.warning("Static HTML file not found on startup - will serve fallback")
    except Exception as e:
        logging.error(f"Error initializing static file cache: {e}")

    if not silent:
        print(f"🌐 Starting SSH Session Manager API Server...")
        print(f"📁 Using config: {config_file}")
        print(f"🚀 Server will be available at http://{host}:{port}")
        print(f"🔧 Static files cached: {'✅' if _static_file_cache['html_exists'] else '❌'}")

    # Configure uvicorn
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="error" if silent else "info",
        access_log=not silent
    )

    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    launch_api_server()
