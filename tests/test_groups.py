"""Group icons and ordering - the metadata that belongs to no single host."""

import json
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groups import GroupStore, normalize_emoji
from main import group_hosts


@pytest.fixture
def store(tmp_path):
    return GroupStore(str(tmp_path / 'hosts.json'))


def test_metadata_lives_beside_the_hosts(tmp_path):
    """Whatever --config points at, the icons follow it - otherwise a test run
    or a second profile would write over the real one."""
    store = GroupStore(str(tmp_path / 'somewhere' / 'hosts.json'))
    assert store.path == tmp_path / 'somewhere' / 'groups.json'


def test_an_absent_file_is_simply_no_metadata(store):
    assert store.read() == ({}, [])
    assert store.emoji_for('Production') == ''
    assert store.metadata(['B', 'A']) == [
        {'name': 'A', 'emoji': ''}, {'name': 'B', 'emoji': ''},
    ]


def test_a_corrupt_file_does_not_take_the_host_list_with_it(store):
    """Decoration must never be able to stop the app listing hosts."""
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text('{ this is not json')

    assert store.read() == ({}, [])
    assert store.metadata(['Production']) == [{'name': 'Production', 'emoji': ''}]


def test_an_icon_survives_a_round_trip(store):
    store.set_emoji('Production', '🚀')
    assert store.emoji_for('Production') == '🚀'
    assert json.loads(store.path.read_text())['groups'] == [
        {'name': 'Production', 'emoji': '🚀'},
    ]


def test_an_icon_does_not_move_the_group(store):
    """Decorating a group is not arranging it - the sidebar order is the
    user's, and giving Production a rocket must not lift it above Databases."""
    store.set_emoji('Production', '🚀')

    assert [g['name'] for g in store.metadata(['Databases', 'Production'])] == [
        'Databases', 'Production',
    ]


def test_multi_codepoint_emoji_are_kept_whole(store):
    """A flag is two codepoints and a family can be seven. Truncating one
    leaves a different emoji, or a pair of stray letters."""
    for emoji in ('🇮🇳', '👨‍👩‍👧‍👦', '👍🏽'):
        store.set_emoji('G', emoji)
        assert store.emoji_for('G') == emoji


@pytest.mark.parametrize('value, expected', [
    ('🚀', '🚀'),
    ('  🚀  ', '🚀'),
    ('', ''),
    (None, ''),
    (123, ''),
    ('a very long label pretending to be an icon', ''),
    ('bad\x00', ''),
    ('two\nlines', ''),
])
def test_only_something_icon_shaped_is_stored(value, expected):
    assert normalize_emoji(value) == expected


# --- ordering ---------------------------------------------------------------

def test_configured_groups_come_first_then_the_rest_alphabetically(store):
    store.set_order(['Zebra', 'Alpha'])

    ordered = [g['name'] for g in store.metadata(['Alpha', 'Zebra', 'Beta', 'Aardvark'])]
    assert ordered == ['Zebra', 'Alpha', 'Aardvark', 'Beta']


def test_reordering_keeps_every_icon(store):
    store.set_emoji('Production', '🚀')
    store.set_emoji('Staging', '🧪')

    store.set_order(['Staging', 'Production'])

    assert [(g['name'], g['emoji']) for g in store.metadata(['Production', 'Staging'])] == [
        ('Staging', '🧪'), ('Production', '🚀'),
    ]


def test_a_stale_tab_cannot_drop_a_group_it_never_saw(store):
    """The browser sends the order it knows about. A group added elsewhere
    since then must keep its icon rather than being reordered out of the file."""
    store.set_emoji('Production', '🚀')
    store.set_emoji('Newcomer', '✨')

    store.set_order(['Production'])

    emoji, order = store.read()
    assert emoji == {'Production': '🚀', 'Newcomer': '✨'}
    assert order == ['Production']


def test_the_host_list_follows_the_same_order(store):
    store.set_order(['Zebra', 'Alpha'])
    hosts = [
        {'name': 'a', 'group': 'Alpha'},
        {'name': 'z', 'group': 'Zebra'},
        {'name': 'b', 'group': 'Beta'},
        {'name': 'u', 'group': ''},
    ]

    groups, ungrouped = group_hosts(hosts, store.order_key)

    assert list(groups) == ['Zebra', 'Alpha', 'Beta']
    assert [h['name'] for h in ungrouped] == ['u']


def test_without_any_arrangement_groups_are_alphabetical():
    """A fresh install has no groups.json, and must still be sorted."""
    hosts = [{'name': 'x', 'group': 'Zebra'}, {'name': 'y', 'group': 'alpha'}]

    groups, _ = group_hosts(hosts)

    assert list(groups) == ['alpha', 'Zebra']


# --- renaming ---------------------------------------------------------------

def test_renaming_carries_the_icon_and_the_position(store):
    store.set_order(['Production', 'Staging'])
    store.set_emoji('Production', '🚀')

    store.rename('Production', 'Prod')

    emoji, order = store.read()
    assert emoji == {'Prod': '🚀'}
    assert order == ['Prod', 'Staging']


def test_renaming_onto_an_existing_entry_leaves_no_duplicate(store):
    store.set_emoji('Production', '🚀')
    store.set_emoji('Prod', '📦')

    store.set_order(['Production', 'Prod'])

    store.rename('Production', 'Prod')

    emoji, order = store.read()
    assert order == ['Prod']
    assert emoji == {'Prod': '🚀'}


def test_forgetting_a_group_removes_only_it(store):
    store.set_emoji('A', '🅰️')
    store.set_emoji('B', '🅱️')

    store.set_order(['A', 'B'])

    store.forget('A')

    emoji, order = store.read()
    assert order == ['B']
    assert list(emoji) == ['B']
