"""Reordering hosts inside a group, which is their order in hosts.json."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_server

client = TestClient(api_server.app)


@pytest.fixture
def hosts(monkeypatch):
    """A host list with two groups interleaved, so a reorder that touches the
    wrong slots is impossible to miss."""
    data = [
        {'name': 'web-1', 'group': 'Production', 'tags': []},
        {'name': 'db-1', 'group': 'Databases', 'tags': []},
        {'name': 'web-2', 'group': 'Production', 'tags': []},
        {'name': 'spare', 'group': '', 'tags': []},
        {'name': 'web-3', 'group': 'Production', 'tags': []},
        {'name': 'db-2', 'group': 'Databases', 'tags': []},
    ]
    config = {'hosts': data}
    monkeypatch.setattr(api_server.api_manager.ssh_manager, 'config', config)
    monkeypatch.setattr(api_server.api_manager, 'all_hosts', data)
    monkeypatch.setattr(api_server.api_manager, 'refresh_hosts_data', lambda: None)
    monkeypatch.setattr(api_server.api_manager.ssh_manager, 'save_config', lambda: True)
    return config


def names(config):
    return [h['name'] for h in config['hosts']]


def test_reordering_a_group_leaves_every_other_host_where_it_was(hosts):
    """The slots Production occupies stay Production's - Databases and the
    ungrouped host must not shift because Production was rearranged."""
    response = client.put('/api/hosts/order', json={
        'group': 'Production', 'hosts': ['web-3', 'web-1', 'web-2'],
    })

    assert response.status_code == 200, response.text
    assert names(hosts) == ['web-3', 'db-1', 'web-1', 'spare', 'web-2', 'db-2']


def test_the_new_order_is_what_the_host_list_returns(hosts):
    client.put('/api/hosts/order', json={
        'group': 'Production', 'hosts': ['web-2', 'web-3', 'web-1'],
    })

    data = client.get('/api/hosts').json()['data']

    assert [h['name'] for h in data['groups']['Production']] == ['web-2', 'web-3', 'web-1']
    assert [h['name'] for h in data['groups']['Databases']] == ['db-1', 'db-2']


def test_ungrouped_hosts_can_be_reordered_too(hosts):
    hosts['hosts'].append({'name': 'loose', 'group': '', 'tags': []})

    response = client.put('/api/hosts/order', json={'group': '', 'hosts': ['loose', 'spare']})

    assert response.status_code == 200
    data = client.get('/api/hosts').json()['data']
    assert [h['name'] for h in data['ungrouped_hosts']] == ['loose', 'spare']


def test_a_host_the_client_never_saw_is_not_dropped(hosts):
    """Another tab can add a host mid-drag. It keeps its place at the end
    rather than vanishing from the file."""
    response = client.put('/api/hosts/order', json={
        'group': 'Production', 'hosts': ['web-2', 'web-1'],
    })

    assert response.status_code == 200
    assert sorted(n for n in names(hosts) if n.startswith('web')) == ['web-1', 'web-2', 'web-3']
    data = client.get('/api/hosts').json()['data']
    assert [h['name'] for h in data['groups']['Production']] == ['web-2', 'web-1', 'web-3']


def test_a_name_from_another_group_is_ignored(hosts):
    """Reordering Production must not be able to reach into Databases."""
    client.put('/api/hosts/order', json={
        'group': 'Production', 'hosts': ['db-1', 'web-3', 'web-1', 'web-2'],
    })

    data = client.get('/api/hosts').json()['data']
    assert [h['name'] for h in data['groups']['Databases']] == ['db-1', 'db-2']
    assert [h['name'] for h in data['groups']['Production']] == ['web-3', 'web-1', 'web-2']


def test_the_order_route_is_not_read_as_a_host_named_order(hosts):
    """/api/hosts/{host_name} would happily match "order" - the routes are
    declared so that it cannot."""
    response = client.put('/api/hosts/order', json={'group': 'Production', 'hosts': ['web-1']})

    assert response.status_code == 200
    assert 'hosts_reordered' in response.json()
