# Connectify - SSH Session Manager for iTerm2

A web-based manager for your SSH sessions, with credentials in an encrypted local vault and iTerm2 profile support.

## Features

- 🔐 **Encrypted credentials vault** - one passcode, no macOS Keychain
- 🎯 **Web-based host management** - add, edit, group and connect
- 🖥️ **iTerm2 integration** with custom profiles
- 🎨 **Bundled iTerm2 profiles** (PERSONAL / NON-PROD / PROD / UI) installed for you
- 🔍 **Smart search and filtering** by name or tags
- 🗂️ **Group-based organization** with per-host tile themes
- 🌐 **Web interface** - Modern tile-based UI for easy host management
- 🚀 **Background UI server** - Always-on web interface

## Requirements

- macOS on **Apple Silicon or Intel** - releases ship a build for each, and the
  installer picks the right one
- **[iTerm2](https://iterm2.com/index.html)** - required. Connectify launches every
  session in iTerm2, so the installer stops if it isn't installed.
- **[iTerm2 browser plugin](https://iterm2.com/browser-plugin.html)** - optional.
  Only needed for the shipped `connectify-UI` profile, which opens the Connectify
  web UI inside iTerm2. The installer warns and continues if it's missing.

## Quick Installation

### One-Line Install (Recommended)

No build required! Downloads pre-built binary:

```bash
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/install.sh | sh
```

The installer shows you what it is doing: the version and architecture being
downloaded with a progress bar, a checklist of requirements (iTerm2, the browser
plugin, OpenSSH), where things are installed, the iTerm2 profiles it sets up and
how to put `~/.local/bin` on your PATH if it isn't. No sudo, no Python and no
build tools needed on your machine.

Already installed? `connectify upgrade` fetches and installs the latest release
with the same UI.

## Usage

Connectify is used from its **web interface** - adding hosts, connecting, groups,
themes and profiles all live there. The `connectify` command exists to run that
server and to diagnose problems.

### Web UI server

```bash
connectify ui start           # Start the server in the background
connectify ui stop            # Stop the server
connectify ui restart         # Restart the server
connectify ui status          # Is it running?
connectify ui logs            # Print the server log
```

Once started, access the UI at: **http://localhost:7890**

### Everything else

```bash
connectify profiles list      # Bundled + available iTerm2 profiles
connectify profiles install   # (Re)install the bundled iTerm2 profiles
connectify doctor             # Diagnostics: server, iTerm2, config, vault
connectify version            # Version information
connectify --help             # Show all commands
```

The web interface provides:
- 🎨 **Tile-based host display** organized by group
- 🔍 **Real-time search** and filtering
- 🖱️ **Click-to-connect** functionality
- 📱 **Responsive design** for desktop and mobile

## iTerm2 Profiles

Connectify ships four ready-made iTerm2 profiles and installs them for you:

| Profile | Badge | Use for |
|---------|-------|---------|
| `connectify-PERSONAL` | PERSONAL | Personal / local machines |
| `connectify-NONPROD` | NON-PROD | Dev, QA and staging boxes |
| `connectify-PROD` | PRODUCTION | Production - hard to miss |
| `connectify-UI` | Local | Opens the Connectify web UI inside iTerm2 (browser profile) |

`connectify-UI` is an iTerm2 *browser* profile pointing at
`http://localhost:7890/`, so it needs the
[iTerm2 browser plugin](https://iterm2.com/browser-plugin.html). Browser
profiles can't host an SSH session, so it is installed but never offered when
configuring a host.

They are installed as [iTerm2 Dynamic Profiles](https://iterm2.com/documentation-dynamic-profiles.html)
into `~/Library/Application Support/iTerm2/DynamicProfiles/` during installation,
so they show up in iTerm2 (and in Connectify) without any manual import. Upgrades
refresh them automatically.

```bash
connectify profiles list      # Bundled profiles + everything iTerm2 offers
connectify profiles install   # (Re)install the bundled profiles
```

Set `CONNECTIFY_SKIP_PROFILE_INSTALL=1` if you'd rather manage profiles yourself.
Uninstalling Connectify removes the `connectify-*` profiles again.

### Choosing a profile for a host

The **iTerm Profile** field in the web UI lists every profile iTerm2 currently
knows about - your own profiles, the shipped
Connectify ones and any other dynamic profiles - so you can use any theme you
already have. The list is searchable, refreshable, and still accepts a manually
typed profile name.

## Credentials Vault

SSH passwords and keys live in a single encrypted file, `~/.connectify/vault.json`,
locked with a passcode you choose. It replaces the macOS Keychain entirely.

- **AES-256-GCM**, with the key derived from your passcode via **scrypt**. The
  passcode is never stored - a wrong one simply fails to decrypt. The file is
  written atomically and is owner-readable only (`0600`).
- Credentials are **named** (`prod-admin`, `laptop-key`) and typed: a *password*,
  or an *SSH key* with an optional passphrase (which is used to unlock the key
  at connect time). Each has an optional description.
- Hosts reference a credential **by name**, so one credential can serve many
  hosts and rotating a password is a single edit.
- A credential can also carry the **username** it logs in with - see below.

Upgrading from a pre-vault install? Connectify drops the old `auth_method`,
`ssh_key_path` and `password` fields from `hosts.json` on startup (keeping the
SSH options they implied) and leaves each host's credential empty - create your
credentials in the vault and pick them on the hosts. Old macOS Keychain entries
are left untouched; remove them from Keychain Access whenever you like.

Open the vault from the 🔒 icon in the toolbar, next to import/export.

### Locking

Connectify asks for the passcode **as soon as you open the app**, on whichever
page you land on, and **locks the vault again when you close it**. The derived
key stays in the server's memory for that tab only and is never written to disk
or handed to the browser, so a reload, a second tab or a restart all start
locked. Pressing **Lock** does the same on demand. Reading, editing and
connecting all require it to be unlocked.

### Managing credentials

The Vault page lists every credential with its type and which hosts use it, and
lets you add, edit and delete them. The same dialog is available from the host
form (the **New** button next to the credential picker), so you can create a
credential without leaving the host you're editing.

- **Duplicate names** are refused. Connectify tells you which credential clashes
  and offers to rename yours, edit the existing one, or delete it.
- **Renaming** a credential updates every host that referenced it.
- **Deleting** is blocked while any host uses the credential - the dialog lists
  those hosts by name. Unused credentials just ask for confirmation.

### Usernames

A credential describes an account, so it can carry the **username** to log in
with as well as the secret to prove it. When a credential has one it **overrides
the username on every host that uses it**, and hosts may leave their own
username empty to inherit it - handy when a fleet shares one login. A host's
username is the fallback for credentials that don't name one, so existing hosts
keep working unchanged.

The host tiles show the login that will actually be used. With the vault locked
Connectify can't read the credential's username yet, so the tile shows a dotted
placeholder until you unlock. One of the two has to supply a username - a
connect with neither is refused rather than quietly falling back to your local
account name.

### How a session is launched

Connectify never types your password anywhere. When you connect:

1. The ssh command line is written to a launcher script in a private `0700`
   directory - it contains no secret, only the FIFO's path.
2. iTerm2 runs that launcher as the session's **command**, so no shell is
   involved: nothing appears in the tab's scrollback, and nothing is recorded in
   `~/.zsh_history`.
3. If a secret is needed, `ssh` asks Connectify's askpass helper
   (`SSH_ASKPASS` + `SSH_ASKPASS_REQUIRE=force`), which reads it once from a
   FIFO. The bytes go from Connectify straight into `ssh` - never to disk, never
   onto a command line.
4. The launcher deletes its directory as soon as ssh exits; a sweep on startup
   clears anything left by a killed session.

Connectify waits for iTerm2 to confirm the tab before reporting success, so the
tile keeps its spinner until the session is really open and a failure is
reported instead of being swallowed. Launches are serialized, so opening several
sessions at once queues them rather than having them race inside iTerm2.

The same mechanism answers **SSH key passphrase** prompts, so passphrase-protected
keys work - store the passphrase alongside the key path in its credential.

This needs OpenSSH 8.4+ for `SSH_ASKPASS_REQUIRE` (macOS Monterey and later).
On something older, ssh simply prompts for the password in the tab as usual.

## Groups and Tile Themes

Hosts are organized by an optional **Group** (e.g. `Production`, `Team A`). The
add/edit form offers the groups already in use and lets you type a new one on the
fly, which then becomes available to every other host. Hosts without a group are
rendered as-is, below the groups - grouping is entirely optional.

Each host also picks its own **Theme**: 🔴 red, 🟢 green, 🟠 orange or the neutral
grey default. Click a dot in the add/edit form; the selected one is ringed. The
theme colours that host's tile in the web UI, replacing the old guesswork based
on tag names.

Tags are unchanged and still used for search and filtering.

## Configuration

Configuration is stored at `~/.connectify/hosts.json`. On first run, a sample configuration is created automatically:

```json
{
  "hosts": [
    {
      "name": "Production Server",
      "hostname": "prod.example.com",
      "username": "admin",
      "port": 22,
      "credential": "prod-admin",
      "iterm_profile": "connectify-PROD",
      "group": "Production",
      "theme": "red",
      "tags": ["production", "web"]
    },
    {
      "name": "Dev Server",
      "hostname": "dev.example.com",
      "username": "developer",
      "port": 2222,
      "credential": "dev-server-key",
      "iterm_profile": "connectify-NONPROD",
      "group": "Development",
      "theme": "green",
      "tags": ["development", "testing"]
    }
  ]
}
```

### Host Configuration Options

| Option | Description | Required |
|--------|-------------|----------|
| `name` | Display name for the host | Yes |
| `hostname` | Server hostname or IP address | Yes |
| `username` | SSH username | Unless the credential has one |
| `port` | SSH port (default: 22) | No |
| `credential` | Name of a credential in the vault | To connect |
| `iterm_profile` | iTerm2 profile name | No |
| `group` | Group used to organize the host list | No |
| `theme` | Tile theme: `default`, `red`, `green` or `orange` | No |
| `tags` | Array of tags for search and filtering | No |

## Auto-Start on Login

The installer will offer to configure the UI server to start automatically when you log in. If you skipped this during installation, you can set it up anytime:

```bash
# Download and run the setup script
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/setup-autostart.sh | bash -s enable

# Or if you have the repo cloned:
./setup-autostart.sh enable

# Check status
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/setup-autostart.sh | bash -s status

# Disable auto-start
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/setup-autostart.sh | bash -s disable
```

The auto-start feature creates a LaunchAgent that:
- Starts the UI server automatically on login
- Keeps the server running in the background
- Restarts the server if it crashes
- Logs output to `/tmp/connectify-autostart.log`

## Uninstallation

### One-Line Uninstall

```bash
curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/connectify-iterm2/main/uninstall.sh | sh
```

### Manual Uninstall

```bash
./uninstall.sh
```

The uninstaller will:
- Stop any running UI server
- Remove installed files
- Optionally remove configuration files
- Guide you through keychain cleanup (for pre-vault installs)

## Advanced Usage

### Custom Port for Temporary UI

```bash
connectify --ui               # Run in the foreground on port 7860 and open a browser
connectify --ui --port 8080   # Foreground on a custom port
connectify --ui --share       # Bind to 0.0.0.0 instead of localhost
```

These run the server in the foreground; `connectify ui start` is the normal way
to run it in the background on port 7890.

### Debugging

```bash
connectify doctor             # Server, iTerm2, profiles, config and vault checks
connectify ui logs            # View UI server logs
```

## Troubleshooting

### Command not found

Make sure `~/.local/bin` is in your PATH:

```bash
echo $PATH | grep ".local/bin"
```

If not, add it to your shell profile:

```bash
# For zsh (default on macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Note**: The installer will offer to do this automatically for you!

### UI server won't start

Check the logs:

```bash
connectify ui logs
```

Make sure port 7890 is not in use:

```bash
lsof -i :7890
```

### Credential issues

Run the diagnostics:

```bash
connectify doctor
```

### iTerm2 not opening

Verify iTerm2 is installed and set as default terminal.

## Security

- Passwords and key passphrases are stored in an AES-256-GCM encrypted vault at
  `~/.connectify/vault.json`, unlocked by your passcode (scrypt-derived key)
- **Secrets are never written to disk to start a session.** They reach `ssh`
  through an askpass helper reading a private FIFO - a kernel rendezvous point
  that stores nothing - so no password file is ever created
- **Secrets never appear on a command line**, so they can't be seen in `ps`
- **Nothing is typed into a shell.** iTerm2 runs the session directly, so the
  SSH command never lands in the terminal scrollback or your shell history
- No `sshpass`: password authentication uses OpenSSH's own `SSH_ASKPASS`
  mechanism, which also unlocks passphrase-protected SSH keys
- UI server runs locally on 127.0.0.1 (not exposed to network by default)

## Requirements

- macOS (Apple Silicon or Intel)
- iTerm2

That's it! No Python or build tools needed for installation.

## Documentation

- **User Guide**: This file
- **Development Guide**: [DEVELOPMENT.md](DEVELOPMENT.md) - For developers who want to contribute

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

## License

MIT License

## Support

- **Repository**: https://github.com/rahulbhooteshwar/connectify-iterm2
- **Issues**: https://github.com/rahulbhooteshwar/connectify-iterm2/issues
- **Discussions**: https://github.com/rahulbhooteshwar/connectify-iterm2/discussions

---

Built with ❤️ by RB (Rahul Bhooteshwar)
