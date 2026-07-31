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

def test_read_hosts_groups_by_group_field(mock_ssh_manager):
    mock_ssh_manager.config = {'hosts': [
        {'name': 'Grouped Host', 'group': 'Production', 'tags': ['test']},
        {'name': 'Loose Host', 'tags': ['test']},
        {'name': 'Blank Group Host', 'group': '  ', 'tags': []},
    ]}

    response = client.get("/api/hosts")
    assert response.status_code == 200
    data = response.json()['data']

    assert list(data['groups']) == ['Production']
    assert [h['name'] for h in data['groups']['Production']] == ['Grouped Host']
    # Hosts without a usable group are returned separately, to be rendered as-is
    assert [h['name'] for h in data['ungrouped_hosts']] == ['Loose Host', 'Blank Group Host']
    assert data['total_hosts'] == 3


def test_groups_endpoint_lists_groups_in_use(mock_ssh_manager):
    mock_ssh_manager.config = {'hosts': [
        {'name': 'a', 'group': 'prod'},
        {'name': 'b', 'group': 'Dev'},
        {'name': 'c', 'group': 'prod'},
        {'name': 'd'},
    ]}

    response = client.get("/api/groups")

    assert response.status_code == 200
    assert response.json()['groups'] == ['Dev', 'prod']

def test_create_host(mock_ssh_manager):
    new_host = {
        "name": "New Host",
        "hostname": "192.168.1.1",
        "username": "user",
        "port": 22,
        "auth_method": "password",
        "credential": "prod-admin",
        "group": " Production ",
        "theme": "RED",
        "tags": ["new"]
    }
    
    mock_ssh_manager.add_host_programmatic.return_value = True
    mock_ssh_manager.get_host.return_value = {k:v for k,v in new_host.items() if k != 'password'}
    
    response = client.post("/api/hosts", json=new_host)
    
    assert response.status_code == 200
    assert response.json()['success'] is True
    mock_ssh_manager.add_host_programmatic.assert_called_once()
    stored = mock_ssh_manager.add_host_programmatic.call_args[0][0]
    assert stored['group'] == 'Production'
    assert stored['theme'] == 'red'
    # Secrets live in the vault now - creating a host never touches them
    assert stored['credential'] == 'prod-admin'
    assert 'password' not in stored
    mock_ssh_manager.store_password.assert_not_called()

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
    # Only what iTerm2 has: a host still naming a deleted profile must not
    # keep that profile alive in the picker
    assert 'Legacy Profile' not in [p['name'] for p in data['profiles']]
    assert not mock_list.call_args.kwargs.get('extra_names')


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
