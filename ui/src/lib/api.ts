/** The one place that talks to the FastAPI backend.
 *
 * The vault token lives in module memory only - never storage - so closing
 * or reloading the page locks the vault, which is the designed behaviour.
 * A 401 with code "vault_locked" clears it and raises VaultLockedError; the
 * store turns that into the unlock dialog and retries.
 */

import type {
  Credential, FullCredential, GroupMeta, Host, HostsPayload, ItermProfile, VaultStatus,
} from './types'

let vaultToken: string | null = null

export function getVaultToken() { return vaultToken }
export function setVaultToken(token: string | null) { vaultToken = token }

export class VaultLockedError extends Error {
  constructor() { super('The vault is locked') }
}

export class ApiError extends Error {
  detail: unknown
  status: number
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : (detail as any)?.message ?? `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) }
  if (init.body) headers['Content-Type'] = 'application/json'
  if (vaultToken) headers['X-Vault-Token'] = vaultToken

  const response = await fetch(path, { ...init, headers })
  const body = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = body?.detail
    if (response.status === 401 && detail?.code === 'vault_locked') {
      vaultToken = null
      throw new VaultLockedError()
    }
    throw new ApiError(response.status, detail ?? body)
  }
  return body as T
}

// --- hosts -------------------------------------------------------------------

export const fetchHosts = () =>
  request<{ data: HostsPayload }>('/api/hosts').then((r) => r.data)

export const createHost = (host: Partial<Host>) =>
  request<{ host: Host }>('/api/hosts', { method: 'POST', body: JSON.stringify(host) })

export const updateHost = (originalName: string, host: Partial<Host>) =>
  request<{ host: Host }>(`/api/hosts/${encodeURIComponent(originalName)}`, {
    method: 'PUT', body: JSON.stringify(host),
  })

export const deleteHost = (name: string) =>
  request(`/api/hosts/${encodeURIComponent(name)}`, { method: 'DELETE' })

export const connectHost = (name: string) =>
  request<{ message: string }>('/api/connect', {
    method: 'POST', body: JSON.stringify({ host_name: name }),
  })

export const importHosts = (hosts: unknown[]) =>
  request<{ message: string; imported_count: number; errors: string[] | null; warnings: string[] | null }>(
    '/api/import/hosts', { method: 'POST', body: JSON.stringify({ hosts }) })

// --- lookups -----------------------------------------------------------------

export const fetchTags = () => request<{ tags: string[] }>('/api/tags').then((r) => r.tags)
export const fetchGroups = () => request<{ groups: string[] }>('/api/groups').then((r) => r.groups)

/** Rename a group and/or set its icon. The rename rewrites every host in it,
 * which is why it is one request rather than a loop over hosts here. */
export const updateGroup = (name: string, changes: { name?: string; emoji?: string }) =>
  request<{ name: string; emoji: string; hosts_updated: number }>(
    `/api/groups/${encodeURIComponent(name)}`,
    { method: 'PUT', body: JSON.stringify(changes) },
  )

/** Persist the order hosts were dragged into within one group. Ungrouped
 * hosts are a group with an empty name. */
export const setHostOrder = (group: string, hosts: string[]) =>
  request<{ hosts_reordered: number }>('/api/hosts/order', {
    method: 'PUT',
    body: JSON.stringify({ group, hosts }),
  })

/** Persist the order the groups were dragged into. */
export const setGroupOrder = (groups: string[]) =>
  request<{ group_meta: GroupMeta[] }>('/api/groups/order', {
    method: 'PUT',
    body: JSON.stringify({ groups }),
  }).then((r) => r.group_meta)
export const fetchProfiles = () =>
  request<{ profiles: ItermProfile[] }>('/api/profiles').then((r) => r.profiles)

// --- vault -------------------------------------------------------------------

export const vaultStatus = () => request<VaultStatus>('/api/vault/status')

export async function vaultCreate(passcode: string) {
  const r = await request<{ token: string }>('/api/vault/create', {
    method: 'POST', body: JSON.stringify({ passcode }),
  })
  vaultToken = r.token
}

export async function vaultUnlock(passcode: string) {
  const r = await request<{ token: string }>('/api/vault/unlock', {
    method: 'POST', body: JSON.stringify({ passcode }),
  })
  vaultToken = r.token
}

export async function vaultLock() {
  try { await request('/api/vault/lock', { method: 'POST' }) } catch { /* already locked */ }
  vaultToken = null
}

export const vaultChangePasscode = (current: string, next: string) =>
  request<{ token: string }>('/api/vault/passcode', {
    method: 'POST', body: JSON.stringify({ current_passcode: current, new_passcode: next }),
  }).then((r) => { vaultToken = r.token })

/** Fired from pagehide: closing the app locks the vault, by design.
 * sendBeacon because ordinary fetches are dropped during unload. */
export function lockBeacon() {
  if (!vaultToken) return
  navigator.sendBeacon?.('/api/vault/lock-beacon',
    new Blob([JSON.stringify({ token: vaultToken })], { type: 'application/json' }))
  vaultToken = null
}

// --- credentials -------------------------------------------------------------

export const fetchCredentials = () =>
  request<{ credentials: Credential[] }>('/api/vault/credentials').then((r) => r.credentials)

export const fetchCredential = (name: string) =>
  request<{ credential: FullCredential }>(`/api/vault/credentials/${encodeURIComponent(name)}`)
    .then((r) => r.credential)

export const createCredential = (payload: Record<string, unknown>) =>
  request<{ message: string }>('/api/vault/credentials', {
    method: 'POST', body: JSON.stringify(payload),
  })

export const updateCredential = (name: string, payload: Record<string, unknown>) =>
  request<{ message: string; renamed_hosts: number }>(
    `/api/vault/credentials/${encodeURIComponent(name)}`,
    { method: 'PUT', body: JSON.stringify(payload) })

export const deleteCredential = (name: string) =>
  request<{ message: string }>(`/api/vault/credentials/${encodeURIComponent(name)}`, { method: 'DELETE' })
