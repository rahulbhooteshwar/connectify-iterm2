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


# --- pre-vault host fields ---------------------------------------------------

def test_legacy_auth_fields_are_stripped_on_startup(tmp_path):
    """Secrets live in the vault, so hosts must not keep describing auth."""
    import json
    from main import SSHManager

    config = tmp_path / "hosts.json"
    config.write_text(json.dumps({"hosts": [
        {"name": "pw-host", "hostname": "a", "username": "u", "port": 22,
         "auth_method": "password", "password": "left-over"},
        {"name": "key-host", "hostname": "b", "username": "u", "port": 22,
         "auth_method": "key", "ssh_key_path": "~/.ssh/id_rsa",
         "ssh_options": ["StrictHostKeyChecking=no"]},
    ]}))

    SSHManager(str(config))
    hosts = {h["name"]: h for h in json.loads(config.read_text())["hosts"]}

    for host in hosts.values():
        assert "auth_method" not in host
        assert "ssh_key_path" not in host
        assert "password" not in host
        assert host["credential"] == "", "credential starts empty - pick one in the vault"

    # The options the auth method used to imply are kept, so connections
    # behave the same as before the fields were dropped
    assert hosts["pw-host"]["ssh_options"] == [
        "PreferredAuthentications=password", "PubkeyAuthentication=no"]
    # An explicit list is left alone
    assert hosts["key-host"]["ssh_options"] == ["StrictHostKeyChecking=no"]


def test_cleanup_leaves_a_modern_config_alone(tmp_path):
    import json
    from main import SSHManager

    config = tmp_path / "hosts.json"
    original = {"hosts": [{"name": "h", "hostname": "a", "username": "u", "port": 22,
                           "credential": "prod-admin", "ssh_options": []}]}
    config.write_text(json.dumps(original))

    manager = SSHManager(str(config))

    assert manager.clean_legacy_host_fields() == 0
    assert json.loads(config.read_text()) == original
