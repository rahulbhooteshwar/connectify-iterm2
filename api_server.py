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

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from main import SSHManager


class HostModel(BaseModel):
    name: str
    hostname: str
    username: str
    port: int = 22
    auth_method: str = "password"
    ssh_key_path: Optional[str] = None
    iterm_profile: str = "Default"
    tags: List[str] = []


class HostCreate(HostModel):
    password: Optional[str] = None


class HostUpdate(HostModel):
    password: Optional[str] = None


class ConnectRequest(BaseModel):
    host_name: str


class SearchRequest(BaseModel):
    search_term: str = ""
    tag_filter: str = ""


class ImportRequest(BaseModel):
    hosts: List[HostCreate]


class APISSHManager:
    def __init__(self, config_file="~/.ssh_manager_config.json"):
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

    def get_unique_tags(self):
        """Get all unique tags from hosts"""
        tags = set()
        for host in self.all_hosts:
            host_tags = host.get('tags', [])
            tags.update(host_tags)
        return sorted(list(tags))

    def get_hosts_by_tag_groups(self, search_term="", tag_filter=""):
        """Get hosts organized by tag groups"""
        hosts = self.get_hosts_data(search_term, tag_filter)

        # Group hosts by tags
        tag_groups = {}
        untagged_hosts = []

        for host in hosts:
            host_tags = host.get('tags', [])
            if not host_tags:
                untagged_hosts.append(host)
            else:
                primary_tag = host_tags[0]
                if primary_tag not in tag_groups:
                    tag_groups[primary_tag] = []
                tag_groups[primary_tag].append(host)

        return {
            "tag_groups": tag_groups,
            "untagged_hosts": untagged_hosts,
            "total_hosts": len(hosts)
        }

    def connect_to_host(self, host_name: str):
        """Connect to host by name"""
        # Find the host
        host = None
        for h in self.all_hosts:
            if h['name'] == host_name:
                host = h
                break

        if not host:
            raise HTTPException(status_code=404, detail=f"Host '{host_name}' not found")

        # Check if password is required but not stored
        if host.get('auth_method') == 'password':
            service_name = f"ssh-{host['hostname']}"
            username = host['username']
            password = self.ssh_manager.get_password(service_name, username)
            
            if not password:
                # Return a special error that the frontend can handle
                raise HTTPException(
                    status_code=400,
                    detail=f"Password required for '{host['name']}'. Please edit the host and set a password first."
                )

        try:
            # Launch the SSH session in a separate thread
            def launch_session():
                try:
                    self.ssh_manager.launch_iterm_session(host)
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

    def add_host(self, host_data: dict, password: str = None):
        """Add a new host"""
        self.ssh_manager.add_host_programmatic(host_data)
        
        if password and host_data.get('auth_method') == 'password':
            service_name = f"ssh-{host_data['hostname']}"
            self.ssh_manager.store_password(service_name, host_data['username'], password)
            
        self.refresh_hosts_data()
        return self.ssh_manager.get_host(host_data['name'])

    def update_host(self, original_name: str, host_data: dict, password: str = None):
        """Update an existing host"""
        self.ssh_manager.update_host(original_name, host_data)
        
        if password and host_data.get('auth_method') == 'password':
            service_name = f"ssh-{host_data['hostname']}"
            self.ssh_manager.store_password(service_name, host_data['username'], password)
            
        self.refresh_hosts_data()
        return self.ssh_manager.get_host(host_data['name'])

    def delete_host(self, host_name: str):
        """Delete a host"""
        self.ssh_manager.delete_host(host_name)
        self.refresh_hosts_data()
        return True

    def get_host_password(self, host_name: str):
        """Get password for a host"""
        host = self.ssh_manager.get_host(host_name)
        if not host:
            raise HTTPException(status_code=404, detail=f"Host '{host_name}' not found")
            
        if host.get('auth_method') != 'password':
            return None
            
        service_name = f"ssh-{host['hostname']}"
        return self.ssh_manager.get_password(service_name, host['username'])
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
        result = api_manager.get_hosts_by_tag_groups(search_term, tag_filter)
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


@app.post("/api/connect")
async def connect_host(request: ConnectRequest, background_tasks: BackgroundTasks):
    """Connect to a specific host"""
    try:
        result = api_manager.connect_to_host(request.host_name)
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
        host_dict = host.dict(exclude={'password'})
        password = host.password
        
        result = api_manager.add_host(host_dict, password)
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
        host_dict = host.dict(exclude={'password'})
        password = host.password
        
        result = api_manager.update_host(host_name, host_dict, password)
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


@app.get("/api/hosts/{host_name}/password")
async def get_host_password(host_name: str):
    """Get password for a host"""
    try:
        password = api_manager.get_host_password(host_name)
        return {
            "success": True,
            "password": password
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetPasswordRequest(BaseModel):
    password: str


@app.post("/api/hosts/{host_name}/password")
async def set_host_password(host_name: str, request: SetPasswordRequest):
    """Set or update password for a host"""
    try:
        host = api_manager.ssh_manager.get_host(host_name)
        if not host:
            raise HTTPException(status_code=404, detail=f"Host '{host_name}' not found")
        
        if host.get('auth_method') != 'password':
            raise HTTPException(status_code=400, detail=f"Host '{host_name}' does not use password authentication")
        
        # Store the password in keychain
        service_name = f"ssh-{host['hostname']}"
        api_manager.ssh_manager.store_password(service_name, host['username'], request.password)
        
        return {
            "success": True,
            "message": f"Password set successfully for '{host_name}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/hosts")
async def export_hosts():
    """Export current host configurations"""
    try:
        hosts = api_manager.all_hosts
        # Remove passwords from export for security
        export_data = []
        for host in hosts:
            host_data = {k: v for k, v in host.items() if k != 'password'}
            export_data.append(host_data)
        
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
                "auth_method": "password",
                "password": "your_password_here",
                "ssh_key_path": None,
                "iterm_profile": "Default",
                "tags": ["production", "web"]
            },
            {
                "name": "Dev Server",
                "hostname": "dev.example.com",
                "username": "developer",
                "port": 2222,
                "auth_method": "key",
                "password": None,
                "ssh_key_path": "~/.ssh/id_rsa",
                "iterm_profile": "Development",
                "tags": ["development", "testing"]
            }
        ],
        "_note": "For password authentication hosts, provide the password in the 'password' field. Passwords will be securely stored in keychain. For key-based auth, set password to null and provide ssh_key_path."
    }
    
    return JSONResponse(
        content=template,
        headers={
            "Content-Disposition": "attachment; filename=ssh_hosts_template.json"
        }
    )


@app.post("/api/import/hosts")
async def import_hosts(import_data: ImportRequest):
    """Import host configurations with password handling"""
    try:
        imported_count = 0
        errors = []
        warnings = []
        
        for host_data in import_data.hosts:
            try:
                # Extract password if present
                password = host_data.password if hasattr(host_data, 'password') else None
                host_dict = host_data.dict(exclude={'password'})
                
                # Validate password requirement
                if host_dict.get('auth_method') == 'password':
                    if password:
                        # Password provided, will be stored in keychain
                        api_manager.add_host(host_dict, password)
                        imported_count += 1
                    else:
                        # No password provided, add warning
                        api_manager.add_host(host_dict, None)
                        warnings.append(f"Host '{host_data.name}' imported without password. You'll need to set the password before connecting.")
                        imported_count += 1
                else:
                    # Key-based authentication, no password needed
                    api_manager.add_host(host_dict, None)
                    imported_count += 1
                    
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


def launch_api_server(config_file="~/.ssh_manager_config.json", port=7860, host="127.0.0.1", silent=False):
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
