import * as React from 'react'
import {
  Github, KeyRound, Lock, LockOpen, Moon, PanelLeftClose, PanelLeftOpen, Server, Sun, Unplug,
} from 'lucide-react'
import { useStore, type Toast } from './store'
import * as api from './lib/api'
import { cn, Tooltip, TooltipProvider } from './components/ui'
import { HostsPage } from './pages/HostsPage'
import { VaultPage } from './pages/VaultPage'
import { VaultGate } from './components/VaultGate'
import { themeById } from './lib/themes'
import { UNGROUPED } from './lib/types'

export type Page = 'hosts' | 'vault'

export default function App() {
  const [page, setPage] = React.useState<Page>('hosts')
  const [groupFilter, setGroupFilter] = React.useState<string | null>(null)

  return (
    <TooltipProvider delayDuration={0}>
    <div className="flex h-full overflow-hidden">
      <Sidebar page={page} setPage={setPage} groupFilter={groupFilter} setGroupFilter={setGroupFilter} />
      <main className="flex min-w-0 flex-1 flex-col">
        {page === 'hosts'
          ? <HostsPage groupFilter={groupFilter} clearGroupFilter={() => setGroupFilter(null)} />
          : <VaultPage />}
      </main>
      <VaultGate />
      <Toasts />
    </div>
    </TooltipProvider>
  )
}

function Sidebar({ page, setPage, groupFilter, setGroupFilter }: {
  page: Page
  setPage: (page: Page) => void
  groupFilter: string | null
  setGroupFilter: (group: string | null) => void
}) {
  const {
    hostsByGroup, hosts, vaultUnlocked, lockVault, openGate, dark, setDark,
    sidebarCollapsed: collapsed, toggleSidebar, reloadHosts, toast,
  } = useStore()
  const counts = new Map(
    hostsByGroup ? Object.entries(hostsByGroup.groups).map(([name, hosts]) => [name, hosts.length]) : [],
  )
  // group_meta is the arranged order; fall back to whatever the host list gave
  // us, so an older backend still renders something sensible
  const meta = hostsByGroup?.group_meta
    ?? [...counts.keys()].map((name) => ({ name, emoji: '' }))
  const groups = meta.filter((g) => counts.has(g.name))
  const ungrouped = hostsByGroup?.ungrouped_hosts.length ?? 0

  // --- drag to reorder ------------------------------------------------------
  // Pointer Events rather than native HTML5 drag-and-drop: the native drag
  // session is a browser/OS-level feature that iTerm2's embedded WebKit view
  // does not reliably provide - dragstart fires but nothing visibly happens,
  // and drop can silently no-op. Pointer Events are just mouse/touch tracking,
  // universally supported, and give full control over the reorder itself.
  const itemRefs = React.useRef(new Map<string, HTMLElement>())
  const dragPointerId = React.useRef<number | null>(null)
  const movedPastThreshold = React.useRef(false)
  const dragStartY = React.useRef(0)
  const [draggingName, setDraggingName] = React.useState<string | null>(null)
  const [liveOrder, setLiveOrder] = React.useState<string[] | null>(null)

  const committedOrder = groups.map((g) => g.name)
  const displayOrder = liveOrder ?? committedOrder
  const displayGroups = displayOrder
    .map((name) => groups.find((g) => g.name === name))
    .filter((g): g is { name: string; emoji: string } => Boolean(g))

  const registerItem = (name: string) => (el: HTMLElement | null) => {
    if (el) itemRefs.current.set(name, el)
    else itemRefs.current.delete(name)
  }

  const beginDrag = (name: string) => (e: React.PointerEvent) => {
    if (e.button !== 0) return
    dragPointerId.current = e.pointerId
    movedPastThreshold.current = false
    dragStartY.current = e.clientY
    setDraggingName(name)
    setLiveOrder(committedOrder)
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  const onDragMove = (e: React.PointerEvent) => {
    if (draggingName === null || e.pointerId !== dragPointerId.current) return
    if (!movedPastThreshold.current && Math.abs(e.clientY - dragStartY.current) > 4) {
      movedPastThreshold.current = true
    }
    const y = e.clientY
    setLiveOrder((current) => {
      if (!current) return current
      const others = current.filter((n) => n !== draggingName)
      let insertAt = others.length
      for (let i = 0; i < others.length; i++) {
        const el = itemRefs.current.get(others[i])
        if (!el) continue
        const mid = el.getBoundingClientRect().top + el.getBoundingClientRect().height / 2
        if (y < mid) { insertAt = i; break }
      }
      const next = [...others]
      next.splice(insertAt, 0, draggingName)
      return next.join('|') === current.join('|') ? current : next
    })
  }

  const endDrag = async () => {
    const name = draggingName
    const moved = movedPastThreshold.current
    const finalOrder = liveOrder
    dragPointerId.current = null
    setDraggingName(null)
    setLiveOrder(null)
    if (!name || !moved || !finalOrder) return
    if (finalOrder.join('|') === committedOrder.join('|')) return
    try {
      await api.setGroupOrder(finalOrder)
      await reloadHosts()
    } catch {
      toast('Could not save the new order', 'error')
    }
  }

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground',
        'transition-[width] duration-200 ease-out',
        collapsed ? 'w-[3.75rem]' : 'w-60',
      )}
    >
      {/* identity */}
      <div className={cn('flex items-center pb-4 pt-5', collapsed ? 'justify-center px-2' : 'gap-2.5 px-4')}>
        <img src="/static/favicon.svg" alt="" className="h-8 w-8 shrink-0 rounded-lg" />
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[15px] font-bold tracking-tight text-foreground">Connectify</div>
            <div className="truncate text-[11px] text-muted-foreground">SSH Session Manager</div>
          </div>
        )}
      </div>

      {/* nav */}
      <nav className="space-y-0.5 px-2.5">
        <NavItem
          active={page === 'hosts'}
          onClick={() => { setPage('hosts'); setGroupFilter(null) }}
          icon={<Server size={16} />}
          label="Hosts"
          badge={hosts.length ? String(hosts.length) : undefined}
          collapsed={collapsed}
        />
        <NavItem
          active={page === 'vault'}
          onClick={() => setPage('vault')}
          icon={<KeyRound size={16} />}
          label="Vault"
          badge={vaultUnlocked ? undefined : '🔒'}
          collapsed={collapsed}
        />
      </nav>

      {/* groups */}
      {groups.length > 0 && (
        <div className={cn(
          'min-h-0 flex-1 overflow-y-auto px-2.5',
          collapsed ? 'mt-3 border-t border-border pt-3' : 'mt-5',
        )}>
          {!collapsed && (
            <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Groups
            </div>
          )}
          {displayGroups.map(({ name, emoji }) => (
            <GroupItem
              key={name}
              itemRef={registerItem(name)}
              name={name}
              emoji={emoji}
              count={counts.get(name) ?? 0}
              color={themeById(hostsByGroup?.groups[name]?.[0]?.theme).color}
              active={groupFilter === name}
              collapsed={collapsed}
              dragging={draggingName === name}
              onPointerDown={beginDrag(name)}
              onPointerMove={onDragMove}
              onPointerUp={endDrag}
              onPointerCancel={endDrag}
              onClick={() => {
                if (movedPastThreshold.current) return
                setPage('hosts')
                setGroupFilter(groupFilter === name ? null : name)
              }}
            />
          ))}
          {ungrouped > 0 && (
            <GroupItem
              name="Ungrouped"
              emoji=""
              count={ungrouped}
              // the neutral theme's own grey: --muted-foreground flips with the
              // colour scheme, which left a dark initial on dark grey in light mode
              color={themeById(undefined).color}
              active={groupFilter === UNGROUPED}
              collapsed={collapsed}
              onClick={() => {
                setPage('hosts')
                setGroupFilter(groupFilter === UNGROUPED ? null : UNGROUPED)
              }}
            />
          )}
        </div>
      )}
      {groups.length === 0 && <div className="flex-1" />}

      {/* footer controls */}
      <div className="space-y-0.5 border-t border-border px-2.5 py-3">
        <NavItem
          onClick={() => (vaultUnlocked ? lockVault() : openGate())}
          icon={vaultUnlocked ? <LockOpen size={16} className="text-success" /> : <Lock size={16} className="text-warning" />}
          label={vaultUnlocked ? 'Lock vault' : 'Unlock vault'}
          collapsed={collapsed}
        />
        <NavItem
          onClick={() => setDark(!dark)}
          icon={dark ? <Sun size={16} /> : <Moon size={16} />}
          label={dark ? 'Light mode' : 'Dark mode'}
          collapsed={collapsed}
        />
        <NavItem
          onClick={toggleSidebar}
          icon={collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          hint="⌘B"
          collapsed={collapsed}
        />
        <MaybeTooltip label="GitHub" collapsed={collapsed}>
          <a
            href="https://github.com/rahulbhooteshwar/connectify-iterm2"
            target="_blank" rel="noopener noreferrer"
            aria-label="GitHub"
            className={cn(
              'flex items-center rounded-lg py-2 text-[13px] transition-colors hover:bg-muted hover:text-foreground',
              collapsed ? 'justify-center px-0' : 'gap-2.5 px-2.5',
            )}
          >
            <Github size={16} />
            {!collapsed && <span className="truncate">GitHub</span>}
          </a>
        </MaybeTooltip>
        {!collapsed && (
          <div className="px-2.5 pt-1.5 text-[10px] text-muted-foreground">
            Built with ❤️ by RB
          </div>
        )}
      </div>
    </aside>
  )
}

function NavItem({ active, onClick, icon, label, badge, hint, collapsed }: {
  active?: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: string
  /** shortcut shown on the right, expanded only */
  hint?: string
  collapsed?: boolean
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        'flex w-full items-center rounded-lg py-2 text-[13px] font-medium cursor-pointer',
        'transition-colors duration-150',
        collapsed ? 'justify-center px-0' : 'gap-2.5 px-2.5',
        active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted hover:text-foreground',
      )}
    >
      {icon}
      {!collapsed && <span className="flex-1 truncate text-left">{label}</span>}
      {!collapsed && badge && <span className="text-[11px] text-muted-foreground">{badge}</span>}
      {!collapsed && hint && (
        <span className="text-[10px] tabular-nums text-muted-foreground/70">{hint}</span>
      )}
    </button>
  )

  // Collapsed to icons, the tooltip is the only label left. The native title
  // attribute has a browser delay and does not reliably render in iTerm2's
  // embedded WebKit browser at all - this shows immediately, everywhere.
  if (!collapsed) return button
  return <Tooltip content={hint ? `${label} (${hint})` : label}>{button}</Tooltip>
}

function GroupItem({
  name, emoji, count, color, active, onClick, collapsed, dragging, itemRef,
  onPointerDown, onPointerMove, onPointerUp, onPointerCancel,
}: {
  name: string
  emoji: string
  count: number
  color: string
  active: boolean
  onClick: () => void
  collapsed?: boolean
  dragging?: boolean
  /** registers this item's element so the drag can measure sibling positions */
  itemRef?: (el: HTMLElement | null) => void
  onPointerDown?: (e: React.PointerEvent) => void
  onPointerMove?: (e: React.PointerEvent) => void
  onPointerUp?: (e: React.PointerEvent) => void
  onPointerCancel?: (e: React.PointerEvent) => void
}) {
  // Array.from, not [0]: an emoji or an accented letter is more than one UTF-16
  // unit, and half of one renders as a replacement character.
  const initial = (Array.from(name.trim())[0] ?? '?').toUpperCase()
  const draggable = Boolean(onPointerDown)

  const button = (
    <button
      ref={itemRef}
      type="button"
      onClick={onClick}
      aria-label={`${name} (${count})`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      className={cn(
        'flex w-full items-center rounded-lg text-[13px] cursor-pointer touch-none select-none',
        'transition-colors duration-150',
        collapsed ? 'justify-center px-0 py-2' : 'gap-2.5 px-2.5 py-1.5',
        active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted hover:text-foreground',
        dragging && 'z-10 opacity-70 shadow-lg',
        draggable && !collapsed && 'cursor-grab active:cursor-grabbing',
      )}
    >
      {collapsed ? (
        // Collapsed there is no room for the name. The icon says which group
        // this is; without one, its initial does, and the tooltip has the rest.
        <span
          aria-hidden
          className={cn(
            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full leading-none',
            emoji ? 'text-sm' : 'text-[11px] font-semibold uppercase',
          )}
          style={emoji ? undefined : { background: color, color: '#0b0d12' }}
        >
          {emoji || initial}
        </span>
      ) : emoji ? (
        <span aria-hidden className="w-4 shrink-0 text-center text-[14px] leading-none">{emoji}</span>
      ) : (
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
      )}
      {!collapsed && <span className="flex-1 truncate text-left">{name}</span>}
      {!collapsed && <span className="text-[11px] tabular-nums text-muted-foreground">{count}</span>}
    </button>
  )

  // Collapsed to icons, the tooltip is the only label left. The native title
  // attribute has a browser delay and does not reliably render in iTerm2's
  // embedded WebKit browser at all - this shows immediately, everywhere.
  if (!collapsed) return button
  return <Tooltip content={`${name} (${count})`}>{button}</Tooltip>
}

/** Wraps in a Tooltip only when collapsed - expanded, the label is already
 * on screen and a second one would just be noise. */
function MaybeTooltip({ label, collapsed, children }: {
  label: string
  collapsed?: boolean
  children: React.ReactElement
}) {
  return collapsed ? <Tooltip content={label}>{children}</Tooltip> : children
}

const toastStyles: Record<Toast['kind'], string> = {
  success: 'text-success',
  error: 'text-destructive',
  info: 'text-muted-foreground',
  locked: 'text-warning',
  unlocked: 'text-success',
}

function Toasts() {
  const { toasts } = useStore()
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-[70]">
      {toasts.map((t, index) => (
        <div
          key={t.id}
          style={{ bottom: `${index * 42}px` }}
          className="absolute left-1/2 -translate-x-1/2 animate-toast-in"
        >
          <div className="flex items-center gap-2 whitespace-nowrap rounded-full border border-border bg-card px-4 py-1.5 text-[13px] text-card-foreground shadow-lg">
            {t.kind === 'locked' && <Lock size={13} className={toastStyles[t.kind]} />}
            {t.kind === 'unlocked' && <LockOpen size={13} className={toastStyles[t.kind]} />}
            {t.kind === 'error' && <Unplug size={13} className={toastStyles[t.kind]} />}
            <span>{t.text}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
