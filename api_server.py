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

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
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


class ConnectRequest(BaseModel):
    host_name: str


class SearchRequest(BaseModel):
    search_term: str = ""
    tag_filter: str = ""


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

        try:
            # Launch the SSH session in a separate thread
            def launch_session():
                self.ssh_manager.launch_iterm_session(host)

            thread = threading.Thread(target=launch_session, daemon=True)
            thread.start()

            return {
                "success": True,
                "message": f"SSH session launched for {host['name']}",
                "host": host
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")


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


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML page"""
    html_file = static_dir / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    else:
        # Return a basic HTML if static files don't exist yet
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SSH Session Manager</title>
        </head>
        <body>
            <h1>SSH Session Manager</h1>
            <p>Static files not found. Please ensure the UI is built properly.</p>
        </body>
        </html>
        """)


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


def launch_api_server(config_file="~/.ssh_manager_config.json", port=7860, host="127.0.0.1", silent=False):
    """Launch the FastAPI server"""
    global api_manager
    api_manager = APISSHManager(config_file)

    if not silent:
        print(f"🌐 Starting SSH Session Manager API Server...")
        print(f"📁 Using config: {config_file}")
        print(f"🚀 Server will be available at http://{host}:{port}")

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
