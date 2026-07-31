import json
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vault as vault_module
from vault import Vault, VaultSessions


PASSCODE = "correct horse battery staple"


@pytest.fixture
def vault(tmp_path):
    return Vault(tmp_path / "vault.json")


@pytest.fixture
def unlocked(vault):
    key = vault.create(PASSCODE)
    return vault, key


# --- encryption --------------------------------------------------------------

def test_create_writes_an_encrypted_file_only_the_owner_can_read(vault):
    key = vault.create(PASSCODE)
    vault.add_credential(key, {
        "name": "prod", "type": "password", "password": "hunter2-super-secret",
    })

    raw = vault.path.read_text()
    assert "hunter2-super-secret" not in raw, "secrets must not hit the disk in the clear"
    assert "prod" not in raw, "credential names are inside the ciphertext too"
    assert oct(os.stat(vault.path).st_mode & 0o777) == "0o600"

    document = json.loads(raw)
    assert document["cipher"] == "AES-256-GCM"
    assert document["kdf"]["name"] == "scrypt"


def test_unlock_round_trip(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "prod", "type": "password", "password": "s3cret"})

    reopened = vault.unlock(PASSCODE)
    assert vault.get_credential(reopened, "prod")["password"] == "s3cret"


def test_wrong_passcode_is_rejected(unlocked):
    vault, _ = unlocked
    with pytest.raises(vault_module.InvalidPasscode):
        vault.unlock("not the passcode")


def test_unlock_before_creation(vault):
    with pytest.raises(vault_module.VaultNotInitialized):
        vault.unlock(PASSCODE)


def test_create_refuses_to_clobber_an_existing_vault(unlocked):
    vault, _ = unlocked
    with pytest.raises(vault_module.VaultError):
        vault.create("another passcode")


def test_locked_operations_raise(unlocked):
    vault, _ = unlocked
    with pytest.raises(vault_module.VaultLocked):
        vault.load(None)


def test_change_passcode(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "prod", "type": "password", "password": "s3cret"})

    new_key = vault.change_passcode(PASSCODE, "a brand new passcode")

    assert vault.get_credential(new_key, "prod")["password"] == "s3cret"
    with pytest.raises(vault_module.InvalidPasscode):
        vault.unlock(PASSCODE)
    assert vault.unlock("a brand new passcode")


def test_change_passcode_requires_the_current_one(unlocked):
    vault, _ = unlocked
    with pytest.raises(vault_module.InvalidPasscode):
        vault.change_passcode("wrong", "new")


# --- credentials -------------------------------------------------------------

def test_add_and_list_credentials(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {
        "name": "prod-admin", "type": "password", "password": "pw", "description": "prod",
    })
    vault.add_credential(key, {
        "name": "laptop-key", "type": "key", "ssh_key_path": "~/.ssh/id_ed25519",
        "passphrase": "pp",
    })

    assert vault.credential_names(key) == ["prod-admin", "laptop-key"]

    key_cred = vault.get_credential(key, "laptop-key")
    assert key_cred["ssh_key_path"] == "~/.ssh/id_ed25519"
    assert key_cred["passphrase"] == "pp"


def test_public_credential_hides_secrets():
    public = vault_module.public_credential({
        "name": "prod", "type": "password", "password": "s3cret", "description": "d",
    }, used_by=["host-a"])

    assert "password" not in public
    assert public["has_password"] is True
    assert public["used_by"] == ["host-a"]

    key_public = vault_module.public_credential({
        "name": "k", "type": "key", "ssh_key_path": "~/.ssh/id_rsa", "passphrase": "pp",
    })
    assert "passphrase" not in key_public
    assert key_public["has_passphrase"] is True
    assert key_public["ssh_key_path"] == "~/.ssh/id_rsa"


def test_a_credential_can_carry_the_username_it_logs_in_with(unlocked):
    vault, key = unlocked
    credential = vault.add_credential(key, {
        "name": "prod-admin", "type": "password", "password": "pw", "username": "  ubuntu ",
    })

    assert credential["username"] == "ubuntu"
    # It is not a secret, so the listing carries it for the tiles to show
    assert vault_module.public_credential(credential)["username"] == "ubuntu"

    # Omitting it on an update keeps it, like the secrets do
    updated, _ = vault.update_credential(key, "prod-admin", {
        "name": "prod-admin", "type": "password",
    })
    assert updated["username"] == "ubuntu"

    # Blanking it explicitly hands the choice back to the hosts
    cleared, _ = vault.update_credential(key, "prod-admin", {
        "name": "prod-admin", "type": "password", "username": "",
    })
    assert cleared["username"] == ""


def test_username_is_optional(unlocked):
    vault, key = unlocked
    credential = vault.add_credential(key, {"name": "k", "type": "password", "password": "pw"})
    assert credential["username"] == ""


@pytest.mark.parametrize("payload,message", [
    ({"name": "", "type": "password", "password": "x"}, "name is required"),
    ({"name": "n", "type": "wat", "password": "x"}, "type must be"),
    ({"name": "n", "type": "password"}, "needs a password"),
    ({"name": "n", "type": "key"}, "needs a key path"),
])
def test_validation(unlocked, payload, message):
    vault, key = unlocked
    with pytest.raises(vault_module.VaultError) as excinfo:
        vault.add_credential(key, payload)
    assert message in str(excinfo.value)


def test_duplicate_names_are_rejected_case_insensitively(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "Prod", "type": "password", "password": "pw"})

    with pytest.raises(vault_module.DuplicateCredentialName) as excinfo:
        vault.add_credential(key, {"name": "  prod ", "type": "password", "password": "pw"})

    assert excinfo.value.name == "Prod", "the caller is told which credential clashes"


def test_key_passphrase_is_optional(unlocked):
    vault, key = unlocked
    credential = vault.add_credential(key, {
        "name": "k", "type": "key", "ssh_key_path": "~/.ssh/id_rsa",
    })
    assert credential["passphrase"] == ""


def test_update_keeps_the_secret_when_it_is_not_resubmitted(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "prod", "type": "password", "password": "s3cret"})

    credential, previous = vault.update_credential(key, "prod", {
        "name": "prod", "type": "password", "description": "now with a description",
    })

    assert previous == "prod"
    assert credential["password"] == "s3cret"
    assert credential["description"] == "now with a description"


def test_update_can_replace_the_secret_and_rename(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "old-name", "type": "password", "password": "old"})

    credential, previous = vault.update_credential(key, "old-name", {
        "name": "new-name", "type": "password", "password": "new",
    })

    assert previous == "old-name"
    assert credential["name"] == "new-name"
    assert credential["password"] == "new"
    assert vault.credential_names(key) == ["new-name"]


def test_update_rejects_a_name_taken_by_another_credential(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "a", "type": "password", "password": "pw"})
    vault.add_credential(key, {"name": "b", "type": "password", "password": "pw"})

    with pytest.raises(vault_module.DuplicateCredentialName):
        vault.update_credential(key, "b", {"name": "a", "type": "password"})


def test_delete_credential(unlocked):
    vault, key = unlocked
    vault.add_credential(key, {"name": "gone", "type": "password", "password": "pw"})

    vault.delete_credential(key, "gone")

    assert vault.credential_names(key) == []
    with pytest.raises(vault_module.CredentialNotFound):
        vault.get_credential(key, "gone")


def test_missing_credential(unlocked):
    vault, key = unlocked
    for call in (lambda: vault.get_credential(key, "nope"),
                 lambda: vault.delete_credential(key, "nope"),
                 lambda: vault.update_credential(key, "nope", {"name": "nope", "type": "password"})):
        with pytest.raises(vault_module.CredentialNotFound):
            call()


# --- sessions ----------------------------------------------------------------

def test_sessions_hand_out_opaque_tokens():
    sessions = VaultSessions()
    token = sessions.create(b"key-material")

    assert isinstance(token, str) and len(token) > 20
    assert sessions.get_key(token) == b"key-material"
    assert sessions.get_key("some other token") is None
    assert sessions.get_key(None) is None


def test_sessions_can_be_revoked():
    sessions = VaultSessions()
    token = sessions.create(b"key")

    assert sessions.revoke(token) is True
    assert sessions.get_key(token) is None
    assert len(sessions) == 0


def test_sessions_expire_when_idle():
    sessions = VaultSessions(idle_timeout=0)
    token = sessions.create(b"key")

    assert sessions.get_key(token) is None, "an idle session must not stay unlocked forever"


def test_revoke_all_locks_every_page():
    sessions = VaultSessions()
    first, second = sessions.create(b"key"), sessions.create(b"key")

    sessions.revoke_all()

    assert sessions.get_key(first) is None
    assert sessions.get_key(second) is None
