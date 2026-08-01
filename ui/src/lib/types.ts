/** What the FastAPI backend stores and serves. Field names are the storage
 * schema (name/hostname/username) - the UI shows Title/Endpoint/Login, but
 * renaming the data would break every existing hosts.json. */

export interface Host {
  name: string
  hostname: string
  username: string
  port: number
  iterm_profile: string
  credential: string
  group: string
  theme: string
  /** optional icon, shown before the title wherever this host's name is rendered */
  emoji: string
  tags: string[]
  ssh_options: string[] | null
  ssh_verbosity: number
}

export interface Credential {
  name: string
  type: 'password' | 'key'
  description: string
  username: string
  created_at?: string
  updated_at?: string
  ssh_key_path?: string
  has_password?: boolean
  has_passphrase?: boolean
  used_by: string[]
}

/** The edit form needs the secret back; only /credentials/{name} carries it */
export interface FullCredential extends Omit<Credential, 'used_by'> {
  password?: string
  passphrase?: string
}

export interface ItermProfile {
  name: string
  guid: string | null
  source: 'iterm2' | 'connectify' | 'dynamic' | 'host' | 'custom'
  is_default: boolean
}

export interface GroupMeta {
  name: string
  /** optional icon, shown before the name wherever the group is rendered */
  emoji: string
}

export interface HostsPayload {
  groups: Record<string, Host[]>
  ungrouped_hosts: Host[]
  total_hosts: number
  /** groups in the order the user arranged them, with their icons */
  group_meta?: GroupMeta[]
}

export interface VaultStatus {
  exists: boolean
  unlocked: boolean
}

export const DEFAULT_SSH_OPTIONS: Record<'password' | 'key', string[]> = {
  password: ['PreferredAuthentications=password,keyboard-interactive', 'PubkeyAuthentication=no'],
  key: ['PreferredAuthentications=publickey', 'PasswordAuthentication=no'],
}

export const SSH_OPTION_DEFS = [
  { flag: 'PreferredAuthentications=password,keyboard-interactive', label: 'Prefer password authentication' },
  { flag: 'PubkeyAuthentication=no', label: 'Disable public key authentication' },
  { flag: 'PreferredAuthentications=publickey', label: 'Prefer public key authentication' },
  { flag: 'PasswordAuthentication=no', label: 'Disable password authentication' },
  { flag: 'StrictHostKeyChecking=no', label: "Skip host key checking (don't prompt on new hosts)" },
]

/** Hosts saved before keyboard-interactive was allowed carry the bare flag */
export const LEGACY_PASSWORD_AUTH = 'PreferredAuthentications=password'
export const PASSWORD_AUTH = 'PreferredAuthentications=password,keyboard-interactive'

/** The login a session actually uses: the credential's wins, the host's is
 * the fallback. Mirrors ssh_session.effective_username on the server. */
export function effectiveLogin(host: Host, credentials: Credential[]): string {
  const cred = credentials.find((c) => c.name === host.credential)
  return (cred?.username || '').trim() || (host.username || '').trim()
}

/** The sidebar's "Ungrouped" filter. A NUL cannot be typed into the group
 * field, so this can never collide with a real group name - and written as an
 * escape it keeps the source plain text. */
export const UNGROUPED = '\u0000ungrouped'
