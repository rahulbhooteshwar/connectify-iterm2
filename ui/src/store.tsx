/** App-wide state: data from the backend, the vault gate, toasts, prefs.
 *
 * One context is enough at this app's size - the data is a few dozen hosts -
 * and it keeps every consumer honest about where state lives.
 */

import * as React from 'react'
import * as api from './lib/api'
import { VaultLockedError } from './lib/api'
import type { Credential, Host, HostsPayload, ItermProfile } from './lib/types'

export interface Toast {
  id: number
  kind: 'success' | 'error' | 'info' | 'warning' | 'locked' | 'unlocked'
  text: string
}

interface StoreShape {
  // data
  hosts: Host[]
  hostsByGroup: HostsPayload | null
  credentials: Credential[]
  tags: string[]
  groups: string[]
  profiles: ItermProfile[]
  reloadHosts: () => Promise<void>
  reloadCredentials: () => Promise<void>
  reloadProfiles: () => Promise<void>

  // vault
  vaultExists: boolean
  vaultUnlocked: boolean
  gateOpen: boolean
  openGate: () => void
  closeGate: () => void
  submitPasscode: (passcode: string, confirm?: string) => Promise<void>
  lockVault: () => Promise<void>
  /** Run a vault operation; on vault_locked, open the gate and retry once
   * the user unlocks. Rejects if they cancel instead. */
  withVault: <T>(operation: () => Promise<T>) => Promise<T>

  // ui
  toasts: Toast[]
  toast: (text: string, kind?: Toast['kind']) => void
  dark: boolean
  setDark: (dark: boolean) => void
  view: 'grid' | 'list'
  setView: (view: 'grid' | 'list') => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
}

const StoreContext = React.createContext<StoreShape | null>(null)

export function useStore(): StoreShape {
  const store = React.useContext(StoreContext)
  if (!store) throw new Error('useStore outside provider')
  return store
}

let toastSeq = 0

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [hostsByGroup, setHostsByGroup] = React.useState<HostsPayload | null>(null)
  const [credentials, setCredentials] = React.useState<Credential[]>([])
  const [tags, setTags] = React.useState<string[]>([])
  const [groups, setGroups] = React.useState<string[]>([])
  const [profiles, setProfiles] = React.useState<ItermProfile[]>([])

  const [vaultExists, setVaultExists] = React.useState(false)
  const [vaultUnlocked, setVaultUnlocked] = React.useState(false)
  const [gateOpen, setGateOpen] = React.useState(false)
  const gateWaiters = React.useRef<{ resolve: () => void; reject: (e: Error) => void }[]>([])

  const [toasts, setToasts] = React.useState<Toast[]>([])
  const [dark, setDarkState] = React.useState(() => document.documentElement.classList.contains('dark'))
  const [view, setViewState] = React.useState<'grid' | 'list'>(
    () => (localStorage.getItem('connectify-view') === 'list' ? 'list' : 'grid'),
  )
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(
    () => localStorage.getItem('connectify-sidebar') === 'collapsed',
  )

  const hosts = React.useMemo(() => {
    if (!hostsByGroup) return []
    return [...Object.values(hostsByGroup.groups).flat(), ...hostsByGroup.ungrouped_hosts]
  }, [hostsByGroup])

  const toast = React.useCallback((text: string, kind: Toast['kind'] = 'info') => {
    const id = ++toastSeq
    setToasts((current) => [...current.slice(-2), { id, kind, text }])
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 3400)
  }, [])

  const reloadHosts = React.useCallback(async () => {
    const [data, tagList, groupList] = await Promise.all([
      api.fetchHosts(), api.fetchTags(), api.fetchGroups(),
    ])
    setHostsByGroup(data)
    setTags(tagList)
    setGroups(groupList)
  }, [])

  const reloadCredentials = React.useCallback(async () => {
    if (!api.getVaultToken()) { setCredentials([]); return }
    try {
      setCredentials(await api.fetchCredentials())
    } catch (e) {
      if (e instanceof VaultLockedError) setCredentials([])
      else throw e
    }
  }, [])

  const reloadProfiles = React.useCallback(async () => {
    try { setProfiles(await api.fetchProfiles()) } catch { setProfiles([]) }
  }, [])

  const openGate = React.useCallback(() => setGateOpen(true), [])

  const closeGate = React.useCallback(() => {
    setGateOpen(false)
    const waiters = gateWaiters.current.splice(0)
    for (const w of waiters) w.reject(new Error('Vault unlock cancelled'))
  }, [])

  const submitPasscode = React.useCallback(async (passcode: string, confirm?: string) => {
    if (!vaultExists) {
      if (passcode !== confirm) throw new Error('The passcodes do not match')
      await api.vaultCreate(passcode)
      setVaultExists(true)
      toast('Vault created', 'unlocked')
    } else {
      await api.vaultUnlock(passcode)
      toast('Vault unlocked', 'unlocked')
    }
    setVaultUnlocked(true)
    setGateOpen(false)
    await reloadCredentials()
    const waiters = gateWaiters.current.splice(0)
    for (const w of waiters) w.resolve()
  }, [vaultExists, reloadCredentials, toast])

  const lockVault = React.useCallback(async () => {
    await api.vaultLock()
    setVaultUnlocked(false)
    setCredentials([])
    toast('Vault locked', 'locked')
  }, [toast])

  const withVault = React.useCallback(async function withVault<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation()
    } catch (e) {
      if (!(e instanceof VaultLockedError)) throw e
      setVaultUnlocked(false)
      setGateOpen(true)
      await new Promise<void>((resolve, reject) => gateWaiters.current.push({ resolve, reject }))
      return await operation()
    }
  }, [])

  const setDark = React.useCallback((value: boolean) => {
    setDarkState(value)
    document.documentElement.classList.toggle('dark', value)
    localStorage.setItem('connectify-color-scheme', value ? 'dark' : 'light')
  }, [])

  const setView = React.useCallback((value: 'grid' | 'list') => {
    setViewState(value)
    localStorage.setItem('connectify-view', value)
  }, [])

  const toggleSidebar = React.useCallback(() => {
    setSidebarCollapsed((collapsed) => {
      localStorage.setItem('connectify-sidebar', collapsed ? 'expanded' : 'collapsed')
      return !collapsed
    })
  }, [])

  // ⌘B / Ctrl+B toggles the sidebar, the way editors do it. Ignored while the
  // caret is in a field, where ⌘B may mean something to the browser and Ctrl+B
  // moves the caret back a character.
  React.useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'b' && e.key !== 'B') return
      if (!e.metaKey && !e.ctrlKey) return
      if (e.altKey) return
      const active = document.activeElement
      if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) return
      e.preventDefault()
      toggleSidebar()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [toggleSidebar])

  // Boot: load everything, then ask for the passcode up front - the vault is
  // locked whenever the app is opened, so get it out of the way immediately.
  React.useEffect(() => {
    (async () => {
      try {
        const status = await api.vaultStatus()
        setVaultExists(status.exists)
        await Promise.all([reloadHosts(), reloadProfiles()])
        setGateOpen(true)
      } catch {
        toast('Could not reach the Connectify server', 'error')
      }
    })()

    // Closing the app locks the vault - any page, by design
    const onPageHide = () => api.lockBeacon()
    window.addEventListener('pagehide', onPageHide)
    return () => window.removeEventListener('pagehide', onPageHide)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const store: StoreShape = {
    hosts, hostsByGroup, credentials, tags, groups, profiles,
    reloadHosts, reloadCredentials, reloadProfiles,
    vaultExists, vaultUnlocked, gateOpen, openGate, closeGate, submitPasscode, lockVault, withVault,
    toasts, toast, dark, setDark, view, setView, sidebarCollapsed, toggleSidebar,
  }

  return <StoreContext.Provider value={store}>{children}</StoreContext.Provider>
}
