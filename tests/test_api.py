import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to import api_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_server import app

client = TestClient(app)

# Mock SSHManager to avoid actual file/keychain operations
@pytest.fixture
def mock_ssh_manager():
    with patch('api_server.api_manager.ssh_manager') as mock:
        # Setup default behavior
        mock.config = {'hosts': []}
        mock.get_host.return_value = None
        yield mock

def test_read_hosts(mock_ssh_manager):
    mock_ssh_manager.config = {'hosts': [{'name': 'Test Host', 'tags': ['test']}]}
    # We need to mock refresh_hosts_data or modify api_manager directly since it loads on init
    from api_server import api_manager
    api_manager.all_hosts = [{'name': 'Test Host', 'tags': ['test']}]
    
    response = client.get("/api/hosts")
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert len(data['data']['tag_groups']['test']) == 1
    assert data['data']['tag_groups']['test'][0]['name'] == 'Test Host'

def test_create_host(mock_ssh_manager):
    new_host = {
        "name": "New Host",
        "hostname": "192.168.1.1",
        "username": "user",
        "port": 22,
        "auth_method": "password",
        "password": "secret_password",
        "tags": ["new"]
    }
    
    mock_ssh_manager.add_host_programmatic.return_value = True
    mock_ssh_manager.get_host.return_value = {k:v for k,v in new_host.items() if k != 'password'}
    
    response = client.post("/api/hosts", json=new_host)
    
    assert response.status_code == 200
    assert response.json()['success'] is True
    mock_ssh_manager.add_host_programmatic.assert_called_once()
    mock_ssh_manager.store_password.assert_called_once_with("ssh-192.168.1.1", "user", "secret_password")

def test_update_host(mock_ssh_manager):
    update_data = {
        "name": "Updated Host",
        "hostname": "192.168.1.2",
        "username": "user",
        "port": 22,
        "auth_method": "key",
        "ssh_key_path": "~/.ssh/id_rsa",
        "tags": ["updated"]
    }
    
    mock_ssh_manager.update_host.return_value = True
    mock_ssh_manager.get_host.return_value = update_data
    
    response = client.put("/api/hosts/Old Host", json=update_data)
    
    assert response.status_code == 200
    assert response.json()['success'] is True
    mock_ssh_manager.update_host.assert_called_once()

def test_get_profiles(mock_ssh_manager):
    """The profile dropdown is fed from iTerm2, not a hardcoded list"""
    mock_ssh_manager.config = {'hosts': [{'name': 'Test Host', 'iterm_profile': 'Legacy Profile'}]}

    discovered = [
        {"name": "Default", "guid": "abc", "source": "iterm2", "is_default": True},
        {"name": "connectify-PROD", "guid": "def", "source": "connectify", "is_default": False},
    ]

    with patch('api_server.iterm_profiles.list_available_profiles', return_value=discovered) as mock_list:
        response = client.get("/api/profiles")

    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert [p['name'] for p in data['profiles']] == ["Default", "connectify-PROD"]
    assert "connectify-PROD" in data['bundled']
    # Profiles already used by hosts are passed through so they stay selectable
    assert mock_list.call_args.kwargs['extra_names'] == ['Legacy Profile']


def test_install_profiles(mock_ssh_manager):
    install_result = {
        "installed": ["connectify-PROD.json"],
        "updated": [],
        "unchanged": [],
        "errors": [],
        "target_dir": "/tmp/DynamicProfiles",
    }

    with patch('api_server.iterm_profiles.install_bundled_profiles', return_value=install_result):
        response = client.post("/api/profiles/install")

    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert "1 profile(s)" in data['message']


def test_delete_host(mock_ssh_manager):
    mock_ssh_manager.delete_host.return_value = True
    
    response = client.delete("/api/hosts/Host To Delete")
    
    assert response.status_code == 200
    assert response.json()['success'] is True
    mock_ssh_manager.delete_host.assert_called_once_with("Host To Delete")
