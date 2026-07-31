import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import group_hosts, normalize_group, normalize_theme


def test_normalize_group_trims_and_defaults_to_empty():
    assert normalize_group("  Production  ") == "Production"
    assert normalize_group("") == ""
    assert normalize_group(None) == ""


def test_normalize_theme_accepts_known_themes_only():
    assert normalize_theme("red") == "red"
    assert normalize_theme("GREEN") == "green"
    assert normalize_theme(" orange ") == "orange"
    assert normalize_theme("default") == "default"
    # Anything unknown or missing falls back to the neutral tile
    assert normalize_theme("purple") == "default"
    assert normalize_theme(None) == "default"
    assert normalize_theme("") == "default"


def test_group_hosts_orders_groups_and_keeps_ungrouped_separate():
    hosts = [
        {"name": "web-1", "group": "prod"},
        {"name": "laptop"},
        {"name": "db-1", "group": "Databases"},
        {"name": "web-2", "group": "prod"},
        {"name": "scratch", "group": "   "},
    ]

    groups, ungrouped = group_hosts(hosts)

    # Case-insensitive alphabetical order
    assert list(groups) == ["Databases", "prod"]
    assert [h["name"] for h in groups["prod"]] == ["web-1", "web-2"]
    # Hosts with no (or a blank) group stay ungrouped, in their original order
    assert [h["name"] for h in ungrouped] == ["laptop", "scratch"]


def test_group_hosts_with_no_groups_at_all():
    hosts = [{"name": "a"}, {"name": "b"}]

    groups, ungrouped = group_hosts(hosts)

    assert groups == {}
    assert [h["name"] for h in ungrouped] == ["a", "b"]
