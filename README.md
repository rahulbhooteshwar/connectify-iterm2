# Connectify - SSH Session Manager for iTerm2

A web-based manager for your SSH sessions, with credentials in an encrypted local vault and iTerm2 profile support.

## Features

- 🔐 **Encrypted credentials vault** - one passcode, no macOS Keychain
- 🎯 **Web-based host management** - add, edit, group and connect
- 🖥️ **iTerm2 integration** with custom profiles
- 🎨 **Bundled iTerm2 profiles** (PERSONAL / NON-PROD / PROD / UI) installed for you
- 🔍 **Smart search and filtering** by name or tags
- 🗂️ **Group-based organization** with per-host tile themes
- 🌐 **Web interface** - sidebar navigation, tile or list view, light and dark
- 💻 **Installs as a desktop app** - the interface is a PWA
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
- 🧭 **A sidebar** for hosts, the vault and your groups
- 🎨 **Tile or list view**, organized by group
- 🔍 **Real-time search** and tag filtering
- 🖱️ **Click-to-connect** functionality
- 🌗 **Light and dark**, following the system until you choose
- 💻 **Install it as a desktop app** from the browser's install button

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

It only ever shows what iTerm2 has right now: delete a profile there (including
a shipped one) and it disappears from the picker on the next refresh, even if
hosts still name it. Such a host keeps its saved value - the form flags it as
*not in iTerm2 any more*, and the session falls back to the default profile
until you pick another.

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

### Why fields have no AutoFill icons

WebKit draws its own buttons inside form fields: a **contact card** on
anything its heuristics read as a person (a field labelled *Name*, a
placeholder mentioning one) and a **key** on password fields. They are painted
over the input, and in iTerm2's embedded browser they stay there once drawn.

Which button appears depends on what the heuristics make of the field, so all
of them are hidden: contacts, credentials, credit card, strong-password,
caps-lock, the datalist arrow and the search-field furniture. On top of that
every text field, and every form, carries `autocomplete="off"`.

None of which was enough on its own. Measured in iTerm2's browser (Safari 26.5) with `tools/field-lab.html`, which
varies one thing at a time across 25 fields. The result: **the visible label
and the element id are what AutoFill reads**. Nothing else moved it - not
`type="search"`, not any `autocomplete` value, not hiding the pseudo-elements,
which the engine simply ignores.

So the fields are named for what they are rather than for a person or a place:
**Title** instead of *Display Name*, **Endpoint** instead of *Hostname / IP*,
**Login** instead of *Username*, with ids to match (`hostTitle`,
`hostEndpoint`, `hostLogin`). Those exact words came back clean where the old
ones drew a contact card and a house. The stored data is unchanged - hosts
still have `name`, `hostname` and `username` in `hosts.json` and the API.

The CSS that hides the AutoFill buttons is still there. It does nothing in
iTerm2's browser, but it costs nothing and works in engines that honour it.
Two details if you touch it:

- **One rule per selector.** A browser that doesn't recognise one selector in a
  list discards the entire list, which would silently take the others with it.
- **The decoration container is left alone.** Collapsing
  `::-webkit-textfield-decoration-container` looks like a tidy catch-all, but
  the field's own text is laid out inside it - a number input renders blank
  while still holding its value.

If you rename a field, keep *name*, *address*, *user*, *phone* and *email* out
of both the label and the id, or the icon comes back. There are tests for it.

### Passcode and password fields

The vault passcode, credential passwords and key passphrases are masked with
CSS (`-webkit-text-security`) on a normal text field rather than being
`type="password"` inputs. Safari - and so iTerm2's embedded browser - paints an
AutoFill key on top of every password field, and in the embedded browser it
never goes away. A field the browser has no reason to decorate avoids that
entirely, and password managers leave it alone.

The mask is a class in the markup, so it applies as the field is parsed - there
is no moment, however brief, where a keystroke could be read. Each field also
*starts* as a password input, so it is masked even before the stylesheet
arrives, and the swap to a text field only happens where the browser is known
to mask it itself. If it isn't supported the fields simply stay password
inputs, and the AutoFill decorations are hidden in CSS as a second line of
defence.

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
   clears anything left by a killed session. The askpass variables are set on
   the `ssh` command itself, not exported, so the shell you are left with in
   that tab can still run `ssh` by hand and prompt normally.

Password logins ask for `PreferredAuthentications=password,keyboard-interactive`.
Both are needed: many servers (anything authenticating through PAM) only offer
**keyboard-interactive**, and asking for `password` alone makes ssh fail with
*"Permission denied (keyboard-interactive)"* without ever prompting. Hosts saved
by an earlier version are updated on startup.

While ssh authenticates, the tab itself is not blank: it prints the host, the
login and which credential is answering, then animates a spinner reading
*connecting...* with the elapsed seconds - one line in the corner, out of the
way of whatever the session prints next. ssh tells Connectify the moment the
session is actually up (via `LocalCommand`), so the spinner gives the line back
before the remote prompt arrives.

Connectify waits for iTerm2 to confirm the tab before reporting success, so the
tile keeps its spinner until the session is really open and a failure is
reported instead of being swallowed. Launches are serialized, so opening several
sessions at once queues them rather than having them race inside iTerm2.

The same mechanism answers **SSH key passphrase** prompts, so passphrase-protected
keys work - store the passphrase alongside the key path in its credential.

### Trusting a new host

`SSH_ASKPASS_REQUIRE=force` routes *every* ssh prompt through the helper -
including the "are you sure you want to continue connecting" question for a
host that isn't in your `known_hosts` yet. That one is a decision, not a
secret, so Connectify never answers it for you: the connecting card steps
aside, ssh's question is shown in the tab with the key fingerprint, and you
type `yes` to trust it. Anything else (including a bare Enter) cancels the
connection. With no terminal to ask, the helper refuses rather than sending
the password to a yes/no prompt.

This needs OpenSSH 8.4+ for `SSH_ASKPASS_REQUIRE` (macOS Monterey and later).
On something older, ssh simply prompts for the password in the tab as usual.

## Groups and Tile Themes

Hosts are organized by an optional **Group** (e.g. `Production`, `Team A`). The
add/edit form offers the groups already in use and lets you type a new one on the
fly, which then becomes available to every other host. Hosts without a group are
rendered as-is, below the groups - grouping is entirely optional.

Each host also picks its own **Theme**: red, orange, amber, green, teal, blue,
violet, pink, or the neutral default. Click a dot in the add/edit form; the
selected one is ringed. The theme colours that host's tile in the web UI, and
its group's dot in the sidebar.

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
| `theme` | Tile theme: `default`, `red`, `orange`, `amber`, `green`, `teal`, `blue`, `violet` or `pink` | No |
| `tags` | Array of tags for search and filtering | No |
| `ssh_options` | Extra `-o` options, e.g. `StrictHostKeyChecking=no` | No |
| `ssh_verbosity` | ssh debug level: `0` (off) to `3` (`-vvv`) | No |

## Auto-Start on Login

The web UI is a background server, so it is worth having it start with your
session. That is a `connectify` command - no script to download:

```bash
connectify autostart           # is it set up?
connectify autostart enable    # start the web UI at login
connectify autostart disable   # stop doing that
```

Enabling it writes a **LaunchAgent** to
`~/Library/LaunchAgents/com.connectify.ui.plist` and loads it, so the server
starts when you log in and logs to `~/Library/Logs/Connectify/`.

The agent runs `connectify --silent`, which *is* the server, in the
foreground - not `connectify ui start`, which spawns it and exits. That
distinction matters more than it looks: with a launcher that exits, launchd
sees the job finish and (with `KeepAlive`) starts it again every ten seconds,
for ever. A process respawning on a timer from a login-persistence entry is
close to the textbook shape of malware, and **endpoint security tools flag
it** - SentinelOne among them. `KeepAlive` is off for the same reason: the
server starts once at login and nothing resurrects it behind your back, so
`connectify ui stop` keeps meaning what it says. The trade-off is that a
crashed server stays down until you start it again.

### When security software objects

A LaunchAgent *is* persistence, and endpoint protection watches persistence -
reasonably, since that is where malware lives. Connectify's binaries are also
not yet signed with an Apple Developer ID, and they run from a hidden
directory in your home folder. On a managed Mac that combination can be
enough to be flagged (SentinelOne files it under *persistence deception*).

The way through is usually to not persist at all:

```bash
connectify autostart enable --shell     # start it from your shell profile
connectify autostart disable --shell    # and take it back out
```

That adds four marked lines to your `~/.zshrc` (or `~/.bash_profile`, or
`config.fish`) which start the server in the background the first time you
open a terminal. `connectify ui start` returns immediately if the server is
already up, so it costs nothing after the first one. No LaunchAgent, no login
hook, nothing for security software to take an interest in. Removing it
restores the file exactly as it was.

If you would rather keep the LaunchAgent, what your IT team needs to allowlist
it is the plist path above, the binary it runs (`~/.local/bin/connectify` →
`~/.local/lib/connectify/connectify`), the release it came from and its
SHA-256 - published as a digest on every
[release](https://github.com/rahulbhooteshwar/connectify-iterm2/releases).

Installing, upgrading and `connectify doctor` all report where you stand, and
say what to run if it isn't on. One case is handled for you: a LaunchAgent that
points at a copy of Connectify a reinstall has moved is repaired during the
install, since you already asked for auto-start once and a broken one fails
silently at every login.

The old `setup-autostart.sh` still works - it now forwards to the command.

### Session scratch files

Each session gets a private `0700` directory under `~/.connectify/run/`
holding two scripts and a FIFO - the ssh command line and the path of the
FIFO the password is passed through. **No credential is ever written there**;
the secret exists only in the vault and in kernel memory as it passes through
the FIFO, and there is a test that fails if any file in that directory ever
contains it.

A session removes its own directory as soon as ssh exits. Anything left by a
tab that was killed outright is swept when the app is opened and before every
launch (older than six hours, so live sessions are left alone).

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

### Verbose logs

Open a host's **Advanced SSH Options** and pick a level next to *Verbose logs*:
`-v`, `-vv` or `-vvv`. That is ssh's own debug stream, and it prints straight
into the session tab above the remote prompt - handy when a connection fails
for reasons the error message does not explain (wrong key offered, host key
mismatch, an option your `~/.ssh/config` sets). The setting is per host and
survives a restart; the collapsed summary line says when it is on, so it is
hard to leave running by accident. With verbose logging on the connecting
spinner steps aside so it cannot overwrite the log.

Note that `-v` is a flag, not an `-o` option, so it has its own control rather
than a checkbox in the list above it.

### "Permission denied (keyboard-interactive)"

The server refused the authentication methods ssh was allowed to try. Open the
host's **Advanced SSH Options** and make sure *Prefer password authentication*
is ticked - it asks for `password,keyboard-interactive`, and servers that
authenticate through PAM accept only the latter. If the host was created by
Connectify 2.0.x, restarting the UI server rewrites the old option for you.

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

Built with ❤️ by RB
