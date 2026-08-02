import * as React from 'react'
import {
  Github, KeyRound, Lock, LockOpen, Moon, PanelLeftClose, PanelLeftOpen, Server, Sun,
  TriangleAlert, Unplug,
} from 'lucide-react'
import { useStore, type Toast } from './store'
import * as api from './lib/api'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { restrictToParentElement, restrictToVerticalAxis } from '@dnd-kit/modifiers'
import {
  SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
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
    <TooltipProvider delayDuration={0} disableHoverableContent>
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
  // dnd-kit rather than hand-rolled pointer maths: it animates the neighbours
  // out of the way as you drag, which is most of what makes a reorder feel
  // like one. It is pointer-event based, so unlike native HTML5 drag-and-drop
  // it works in iTerm2's embedded WebKit view.
  const [pending, setPending] = React.useState<string[] | null>(null)
  const committed = groups.map((g) => g.name)
  const order = pending ?? committed
  const shown = order
    .map((name) => groups.find((g) => g.name === name))
    .filter((g): g is { name: string; emoji: string } => Boolean(g))

  const sensors = useSensors(
    // a few pixels of travel before it counts as a drag, so a plain click on a
    // group still filters instead of being swallowed
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const onDragEnd = async ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const next = arrayMove(order, order.indexOf(String(active.id)), order.indexOf(String(over.id)))
    setPending(next)                       // hold the new order while the server catches up
    try {
      await api.setGroupOrder(next)
      await reloadHosts()
    } catch {
      toast('Could not save the new order', 'error')
    } finally {
      setPending(null)
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
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis, restrictToParentElement]}
            onDragEnd={onDragEnd}
          >
            <SortableContext items={order} strategy={verticalListSortingStrategy}>
              {shown.map(({ name, emoji }) => (
                <SortableGroupItem
                  key={name}
                  name={name}
                  emoji={emoji}
                  count={counts.get(name) ?? 0}
                  color={themeById(hostsByGroup?.groups[name]?.[0]?.theme).color}
                  active={groupFilter === name}
                  collapsed={collapsed}
                  onClick={() => {
                    setPage('hosts')
                    setGroupFilter(groupFilter === name ? null : name)
                  }}
                />
              ))}
            </SortableContext>
          </DndContext>
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

/** A group in the sidebar, made draggable by dnd-kit.
 *
 * The sortable hook supplies the transform that slides this row out of the way
 * as another is dragged past it - that motion is most of what makes a reorder
 * feel like one, and it is why this is a library rather than pointer maths.
 */
function SortableGroupItem(props: {
  name: string
  emoji: string
  count: number
  color: string
  active: boolean
  collapsed?: boolean
  onClick: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: props.name })

  return (
    <GroupItem
      {...props}
      itemRef={setNodeRef}
      dragging={isDragging}
      dragProps={{ ...attributes, ...listeners }}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        // the row being dragged rides above the ones sliding past it
        zIndex: isDragging ? 1 : undefined,
        position: isDragging ? 'relative' : undefined,
      }}
    />
  )
}

function GroupItem({
  name, emoji, count, color, active, onClick, collapsed, dragging,
  itemRef, dragProps, style,
}: {
  name: string
  emoji: string
  count: number
  color: string
  active: boolean
  onClick: () => void
  collapsed?: boolean
  dragging?: boolean
  itemRef?: (el: HTMLElement | null) => void
  /** dnd-kit's listeners and a11y attributes; absent on rows that cannot move */
  dragProps?: Record<string, unknown>
  style?: React.CSSProperties
}) {
  // Array.from, not [0]: an emoji or an accented letter is more than one UTF-16
  // unit, and half of one renders as a replacement character.
  const initial = (Array.from(name.trim())[0] ?? '?').toUpperCase()

  const button = (
    <button
      ref={itemRef}
      type="button"
      onClick={onClick}
      aria-label={`${name} (${count})`}
      style={style}
      {...dragProps}
      className={cn(
        'flex w-full items-center rounded-lg text-[13px] cursor-pointer touch-none select-none',
        'transition-colors duration-150',
        collapsed ? 'justify-center px-0 py-2' : 'gap-2.5 px-2.5 py-1.5',
        active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted hover:text-foreground',
        dragging && 'bg-muted opacity-90 shadow-lg',
        dragProps && !collapsed && 'cursor-grab active:cursor-grabbing',
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
  warning: 'text-warning',
  locked: 'text-warning',
  unlocked: 'text-success',
}

function Toasts() {
  const { toasts } = useStore()
  return (
    /* A flex column rather than stacked absolute offsets: advice toasts wrap
       to two lines, and a fixed per-toast offset would overlap them */
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-[70] flex flex-col-reverse items-center gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="animate-toast-in">
          {/* Advice can run long - it wraps rather than pushing off-screen,
              while the short confirmations keep their single-line pill */}
          <div className="flex max-w-[min(30rem,calc(100vw-2rem))] items-center gap-2 rounded-2xl border border-border bg-card px-4 py-1.5 text-[13px] text-card-foreground shadow-lg">
            {t.kind === 'locked' && <Lock size={13} className={toastStyles[t.kind]} />}
            {t.kind === 'unlocked' && <LockOpen size={13} className={toastStyles[t.kind]} />}
            {t.kind === 'error' && <Unplug size={13} className={toastStyles[t.kind]} />}
            {t.kind === 'warning' && <TriangleAlert size={13} className={`shrink-0 ${toastStyles[t.kind]}`} />}
            <span>{t.text}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
