"""The group endpoints: renaming across hosts, icons, and ordering."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_server
from groups import GroupStore

client = TestClient(api_server.app)


@pytest.fixture
def hosts(tmp_path, monkeypatch):
    """A live group store on a temp path, and a small host list behind it."""
    store = GroupStore(str(tmp_path / 'hosts.json'))
    monkeypatch.setattr(api_server.api_manager, 'group_store', store)

    data = [
        {'name': 'web-1', 'group': 'Production', 'tags': []},
        {'name': 'web-2', 'group': 'Production', 'tags': []},
        {'name': 'db-1', 'group': 'Databases', 'tags': []},
        {'name': 'spare', 'group': '', 'tags': []},
    ]
    monkeypatch.setattr(api_server.api_manager, 'all_hosts', data)
    monkeypatch.setattr(api_server.api_manager, 'refresh_hosts_data', lambda: None)
    monkeypatch.setattr(api_server.api_manager.ssh_manager, 'save_config', lambda: True)
    return data


def test_groups_come_back_with_their_icons(hosts):
    api_server.api_manager.group_store.set_emoji('Production', '🚀')

    body = client.get('/api/groups').json()

    assert body['success'] is True
    assert body['group_meta'] == [
        {'name': 'Databases', 'emoji': ''},
        {'name': 'Production', 'emoji': '🚀'},
    ]


def test_setting_an_icon_leaves_the_hosts_alone(hosts):
    response = client.put('/api/groups/Production', json={'emoji': '🚀'})

    assert response.status_code == 200
    assert response.json()['emoji'] == '🚀'
    assert response.json()['hosts_updated'] == 0
    assert [h['group'] for h in hosts] == ['Production', 'Production', 'Databases', '']


def test_renaming_moves_every_host_in_the_group(hosts):
    response = client.put('/api/groups/Production', json={'name': 'Prod'})

    assert response.status_code == 200
    assert response.json()['hosts_updated'] == 2
    assert [h['group'] for h in hosts] == ['Prod', 'Prod', 'Databases', '']


def test_renaming_carries_the_icon_across(hosts):
    client.put('/api/groups/Production', json={'emoji': '🚀'})

    client.put('/api/groups/Production', json={'name': 'Prod'})

    assert api_server.api_manager.group_store.emoji_for('Prod') == '🚀'


def test_a_rename_can_set_the_icon_at_the_same_time(hosts):
    response = client.put('/api/groups/Production', json={'name': 'Prod', 'emoji': '🔥'})

    assert response.json() == {
        'success': True, 'name': 'Prod', 'emoji': '🔥', 'hosts_updated': 2,
    }


def test_renaming_onto_another_group_is_refused(hosts):
    """Silently merging two groups is not what anyone means by 'rename'."""
    response = client.put('/api/groups/Production', json={'name': 'Databases'})

    assert response.status_code == 409
    assert 'already exists' in response.json()['detail']
    assert [h['group'] for h in hosts] == ['Production', 'Production', 'Databases', '']


def test_renaming_a_group_to_itself_is_harmless(hosts):
    response = client.put('/api/groups/Production', json={'name': 'Production'})

    assert response.status_code == 200
    assert response.json()['hosts_updated'] == 0


def test_a_group_cannot_be_renamed_to_nothing(hosts):
    response = client.put('/api/groups/Production', json={'name': '   '})

    assert response.status_code == 409
    assert [h['group'] for h in hosts] == ['Production', 'Production', 'Databases', '']


def test_renaming_a_group_nobody_uses_is_refused(hosts):
    response = client.put('/api/groups/Nope', json={'name': 'Something'})

    assert response.status_code == 409


def test_the_order_endpoint_is_not_read_as_a_group_named_order(hosts):
    """/api/groups/{name} would happily match "order" - the routes are
    declared so that it cannot."""
    response = client.put('/api/groups/order', json={'groups': ['Databases', 'Production']})

    assert response.status_code == 200
    assert [g['name'] for g in response.json()['group_meta']] == ['Databases', 'Production']


def test_the_host_list_comes_back_in_that_order(hosts):
    client.put('/api/groups/order', json={'groups': ['Production', 'Databases']})
    first = client.get('/api/hosts').json()['data']
    assert list(first['groups']) == ['Production', 'Databases']

    client.put('/api/groups/order', json={'groups': ['Databases', 'Production']})
    second = client.get('/api/hosts').json()['data']
    assert list(second['groups']) == ['Databases', 'Production']


def test_the_host_list_carries_the_icons(hosts):
    client.put('/api/groups/Databases', json={'emoji': '🗄️'})

    data = client.get('/api/hosts').json()['data']

    assert {g['name']: g['emoji'] for g in data['group_meta']}['Databases'] == '🗄️'
