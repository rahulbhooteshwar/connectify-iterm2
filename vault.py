#!/usr/bin/env python3
"""
Connectify credentials vault.

A single encrypted file in ~/.connectify holding named credentials (SSH
passwords and keys), replacing the macOS Keychain. The file is encrypted with
AES-256-GCM using a key derived from the user's passcode with scrypt; the
passcode itself is never stored, and a wrong passcode simply fails the GCM
authentication check.

The vault is locked at rest. Callers unlock it once (getting a derived key),
then read and write through that key.
"""

import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_VAULT_PATH = "~/.connectify/vault.json"

VAULT_FORMAT_VERSION = 1
CREDENTIAL_TYPES = ('password', 'key')
MAX_NAME_LENGTH = 64

# scrypt parameters: ~100ms and 32 MB on a modern Mac, which is plenty for an
# interactive unlock and expensive enough to make guessing painful.
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12

# How long an unlocked session survives without being used
SESSION_IDLE_TIMEOUT = 8 * 60 * 60


class VaultError(Exception):
    """Base class for vault problems that callers are expected to handle."""


class VaultLocked(VaultError):
    """Raised when an operation needs an unlocked vault and didn't get one."""


class VaultNotInitialized(VaultError):
    """Raised when the vault file doesn't exist yet."""


class InvalidPasscode(VaultError):
    """Raised when the supplied passcode can't decrypt the vault."""


class CredentialNotFound(VaultError):
    def __init__(self, name):
        super().__init__(f"Credential '{name}' not found")
        self.name = name


class DuplicateCredentialName(VaultError):
    def __init__(self, name):
        super().__init__(f"A credential named '{name}' already exists")
        self.name = name


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def _unb64(text):
    return base64.b64decode(text.encode('ascii'))


def normalize_name(value):
    """Credential names are trimmed; comparison is case-insensitive."""
    return str(value or '').strip()


def validate_credential(data, existing_names=(), original_name=None):
    """Validate and normalize a credential payload.

    ``existing_names`` is used for the duplicate-name check;  ``original_name``
    is the name being edited, which is allowed to keep its own name.
    """
    name = normalize_name(data.get('name'))
    if not name:
        raise VaultError("Credential name is required")
    if len(name) > MAX_NAME_LENGTH:
        raise VaultError(f"Credential name must be at most {MAX_NAME_LENGTH} characters")

    cred_type = str(data.get('type') or '').strip().lower()
    if cred_type not in CREDENTIAL_TYPES:
        raise VaultError(f"Credential type must be one of: {', '.join(CREDENTIAL_TYPES)}")

    lowered = name.lower()
    for other in existing_names:
        if other.lower() == lowered and (original_name is None or other != original_name):
            raise DuplicateCredentialName(other)

    credential = {
        'name': name,
        'type': cred_type,
        'description': str(data.get('description') or '').strip(),
        # Optional login this credential belongs to. When set it wins over the
        # host's own username, so one credential can carry "who am I" as well
        # as "how do I prove it".
        'username': str(data.get('username') or '').strip(),
    }

    if cred_type == 'password':
        password = data.get('password')
        if not password:
            raise VaultError("A password credential needs a password")
        credential['password'] = str(password)
    else:
        key_path = str(data.get('ssh_key_path') or '').strip()
        if not key_path:
            raise VaultError("An SSH key credential needs a key path")
        credential['ssh_key_path'] = key_path
        # Passphrase is optional - plenty of keys don't have one
        credential['passphrase'] = str(data.get('passphrase') or '')

    return credential


def public_credential(credential, used_by=None):
    """Strip the secrets from a credential so it can be listed safely."""
    public = {
        'name': credential.get('name'),
        'type': credential.get('type'),
        'description': credential.get('description', ''),
        # Not a secret, and the UI needs it to show what a host will connect as
        'username': credential.get('username', ''),
        'created_at': credential.get('created_at'),
        'updated_at': credential.get('updated_at'),
    }

    if credential.get('type') == 'key':
        public['ssh_key_path'] = credential.get('ssh_key_path', '')
        public['has_passphrase'] = bool(credential.get('passphrase'))
    else:
        public['has_password'] = bool(credential.get('password'))

    if used_by is not None:
        public['used_by'] = list(used_by)

    return public


class Vault:
    """The encrypted credentials file."""

    def __init__(self, path=DEFAULT_VAULT_PATH):
        self.path = Path(path).expanduser()

    # --- file level -------------------------------------------------------

    def exists(self):
        return self.path.exists()

    def _read_file(self):
        if not self.exists():
            raise VaultNotInitialized("The vault has not been created yet")
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise VaultError(f"Could not read the vault file: {e}")

    def _write_file(self, document):
        """Write the vault atomically, owner-readable only."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix('.tmp')

        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(document, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        os.replace(tmp_path, self.path)
        os.chmod(self.path, 0o600)

    # --- crypto -----------------------------------------------------------

    @staticmethod
    def _derive_key(passcode, salt, params=None):
        params = params or {}
        return hashlib.scrypt(
            str(passcode).encode('utf-8'),
            salt=salt,
            n=params.get('n', SCRYPT_N),
            r=params.get('r', SCRYPT_R),
            p=params.get('p', SCRYPT_P),
            dklen=params.get('dklen', KEY_LENGTH),
            maxmem=256 * 1024 * 1024,
        )

    def _encrypt(self, key, payload, document=None):
        nonce = secrets.token_bytes(NONCE_LENGTH)
        plaintext = json.dumps(payload).encode('utf-8')
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)

        base = dict(document or {})
        base.update({
            'nonce': _b64(nonce),
            'ciphertext': _b64(ciphertext),
            'updated_at': _now(),
        })
        return base

    def _decrypt(self, key, document):
        try:
            plaintext = AESGCM(key).decrypt(
                _unb64(document['nonce']),
                _unb64(document['ciphertext']),
                None,
            )
        except (InvalidTag, KeyError, ValueError):
            raise InvalidPasscode("Incorrect passcode")
        return json.loads(plaintext.decode('utf-8'))

    # --- lifecycle --------------------------------------------------------

    def create(self, passcode, credentials=None):
        """Create a new vault and return the derived key.

        Refuses to clobber an existing vault - that would throw away every
        stored credential.
        """
        if not passcode:
            raise VaultError("A passcode is required to create the vault")
        if self.exists():
            raise VaultError("The vault already exists")

        salt = secrets.token_bytes(SALT_LENGTH)
        key = self._derive_key(passcode, salt)

        document = self._encrypt(key, {'credentials': list(credentials or [])}, {
            'version': VAULT_FORMAT_VERSION,
            'kdf': {
                'name': 'scrypt',
                'salt': _b64(salt),
                'n': SCRYPT_N,
                'r': SCRYPT_R,
                'p': SCRYPT_P,
                'dklen': KEY_LENGTH,
            },
            'cipher': 'AES-256-GCM',
            'created_at': _now(),
        })
        self._write_file(document)
        return key

    def unlock(self, passcode):
        """Derive and verify the key for ``passcode``."""
        document = self._read_file()
        kdf = document.get('kdf') or {}
        if kdf.get('name') != 'scrypt':
            raise VaultError(f"Unsupported key derivation: {kdf.get('name')}")

        key = self._derive_key(passcode, _unb64(kdf['salt']), kdf)
        # Decrypting is what actually verifies the passcode
        self._decrypt(key, document)
        return key

    def change_passcode(self, current_passcode, new_passcode):
        """Re-encrypt the vault under a new passcode; returns the new key."""
        if not new_passcode:
            raise VaultError("A new passcode is required")

        key = self.unlock(current_passcode)
        payload = self.load(key)

        salt = secrets.token_bytes(SALT_LENGTH)
        new_key = self._derive_key(new_passcode, salt)
        document = self._read_file()
        document['kdf'] = {
            'name': 'scrypt',
            'salt': _b64(salt),
            'n': SCRYPT_N,
            'r': SCRYPT_R,
            'p': SCRYPT_P,
            'dklen': KEY_LENGTH,
        }
        self._write_file(self._encrypt(new_key, payload, document))
        return new_key

    # --- payload ----------------------------------------------------------

    def load(self, key):
        if key is None:
            raise VaultLocked("The vault is locked")
        payload = self._decrypt(key, self._read_file())
        payload.setdefault('credentials', [])
        return payload

    def save(self, key, payload):
        if key is None:
            raise VaultLocked("The vault is locked")
        self._write_file(self._encrypt(key, payload, self._read_file()))

    # --- credentials ------------------------------------------------------

    def list_credentials(self, key):
        return list(self.load(key)['credentials'])

    def credential_names(self, key):
        return [c['name'] for c in self.load(key)['credentials']]

    def get_credential(self, key, name):
        wanted = normalize_name(name).lower()
        for credential in self.load(key)['credentials']:
            if credential['name'].lower() == wanted:
                return credential
        raise CredentialNotFound(name)

    def add_credential(self, key, data):
        payload = self.load(key)
        existing = [c['name'] for c in payload['credentials']]

        credential = validate_credential(data, existing_names=existing)
        credential['created_at'] = _now()
        credential['updated_at'] = credential['created_at']

        payload['credentials'].append(credential)
        self.save(key, payload)
        return credential

    def update_credential(self, key, name, data):
        """Update a credential. Returns ``(credential, previous_name)``."""
        payload = self.load(key)
        existing = [c['name'] for c in payload['credentials']]

        index = next(
            (i for i, c in enumerate(payload['credentials'])
             if c['name'].lower() == normalize_name(name).lower()),
            None,
        )
        if index is None:
            raise CredentialNotFound(name)

        previous = payload['credentials'][index]
        merged = dict(data)
        merged.setdefault('name', previous['name'])
        merged.setdefault('type', previous['type'])
        if merged.get('username') is None:
            merged['username'] = previous.get('username', '')

        # Secrets are optional on update - an omitted value keeps the stored one
        if merged.get('type') == previous.get('type'):
            if merged['type'] == 'password' and not merged.get('password'):
                merged['password'] = previous.get('password')
            if merged['type'] == 'key':
                if not merged.get('ssh_key_path'):
                    merged['ssh_key_path'] = previous.get('ssh_key_path')
                if merged.get('passphrase') is None:
                    merged['passphrase'] = previous.get('passphrase', '')

        credential = validate_credential(
            merged, existing_names=existing, original_name=previous['name']
        )
        credential['created_at'] = previous.get('created_at')
        credential['updated_at'] = _now()

        payload['credentials'][index] = credential
        self.save(key, payload)
        return credential, previous['name']

    def delete_credential(self, key, name):
        payload = self.load(key)
        wanted = normalize_name(name).lower()
        remaining = [c for c in payload['credentials'] if c['name'].lower() != wanted]

        if len(remaining) == len(payload['credentials']):
            raise CredentialNotFound(name)

        payload['credentials'] = remaining
        self.save(key, payload)
        return True


class VaultSessions:
    """In-memory unlocked sessions, keyed by an opaque token.

    The derived key only ever lives here, in the server process. Tokens are
    handed to the browser tab that unlocked the vault and are never persisted,
    so reloading the page locks the vault again.
    """

    def __init__(self, idle_timeout=SESSION_IDLE_TIMEOUT):
        self.idle_timeout = idle_timeout
        self._sessions = {}

    def create(self, key):
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[token] = {'key': key, 'created': now, 'last_used': now}
        return token

    def get_key(self, token):
        self._expire()
        session = self._sessions.get(token or '')
        if not session:
            return None
        session['last_used'] = time.time()
        return session['key']

    def revoke(self, token):
        return self._sessions.pop(token or '', None) is not None

    def revoke_all(self):
        self._sessions.clear()

    def _expire(self):
        cutoff = time.time() - self.idle_timeout
        for token, session in list(self._sessions.items()):
            if session['last_used'] < cutoff:
                del self._sessions[token]

    def __len__(self):
        self._expire()
        return len(self._sessions)
