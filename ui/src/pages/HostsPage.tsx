import * as React from 'react'
import {
  Check, Copy, Download, FolderOpen, KeyRound, LayoutGrid, List, Pencil, Plus,
  RefreshCw, Rocket, Search, SquareAsterisk, Tag, Terminal, Trash2, TriangleAlert, Upload, X,
} from 'lucide-react'
import { useStore } from '../store'
import * as api from '../lib/api'
import { copyText } from '../lib/clipboard'
import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor,
  closestCenter, useSensor, useSensors, type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, arrayMove, rectSortingStrategy, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { effectiveLogin, UNGROUPED, type Host } from '../lib/types'
import { themeById } from '../lib/themes'
import { Badge, Button, cn, Input, Spinner } from '../components/ui'
import { HostDialog } from '../components/HostDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { GroupDialog } from '../components/GroupDialog'
import { ImportDialog, ExportDialog } from '../components/TransferDialogs'

type LaunchState = 'connecting' | 'launched' | undefined

/** A group's icon and a trailing space, or nothing at all. */
function groupIcon(payload: { group_meta?: { name: string; emoji: string }[] } | null, name: string) {
  const emoji = payload?.group_meta?.find((g) => g.name === name)?.emoji
  return emoji ? `${emoji} ` : ''
}

export function HostsPage({ groupFilter, clearGroupFilter }: {
  groupFilter: string | null
  clearGroupFilter: () => void
}) {
  const store = useStore()
  const { hostsByGroup, credentials, tags, view, setView, toast, reloadHosts, withVault, gateOpen } = store
  const searchRef = React.useRef<HTMLInputElement>(null)

  const [search, setSearch] = React.useState('')
  const [tagFilter, setTagFilter] = React.useState('')
  const [launching, setLaunching] = React.useState<Record<string, LaunchState>>({})
  const [editing, setEditing] = React.useState<Host | null | 'new'>(null)
  const [deleting, setDeleting] = React.useState<Host | null>(null)
  const [editingGroup, setEditingGroup] =
    React.useState<{ name: string; emoji: string; count: number } | null>(null)
  const [dragged, setDragged] = React.useState<Host | null>(null)
  const [importing, setImporting] = React.useState(false)
  const [exporting, setExporting] = React.useState(false)

  /* Landing on the host list means you are looking for a host, so typing should
   * go straight into the search box - on first load, and again on the way back
   * from the vault, since this page unmounts while that one is up.
   *
   * Not `autoFocus`: on a locked vault the unlock dialog is up at the same
   * moment and owns the focus. Waiting for the gate to close, and standing down
   * if any dialog is on screen, keeps this from fighting a focus trap for the
   * caret. */
  React.useEffect(() => {
    if (gateOpen) return
    const frame = requestAnimationFrame(() => {
      if (document.querySelector('[role="dialog"]')) return
      searchRef.current?.focus()
    })
    return () => cancelAnimationFrame(frame)
  }, [gateOpen])

  const matches = React.useCallback((host: Host) => {
    if (tagFilter && !(host.tags ?? []).includes(tagFilter)) return false
    const term = search.trim().toLowerCase()
    if (!term) return true
    const haystack = [
      host.name, host.hostname, host.username, effectiveLogin(host, credentials),
      host.group ?? '', ...(host.tags ?? []),
    ].join(' ').toLowerCase()
    return haystack.includes(term)
  }, [search, tagFilter, credentials])

  const sections = React.useMemo(() => {
    if (!hostsByGroup) return []
    // The backend already returns the groups in the arranged order; group_meta
    // carries each one's icon alongside it.
    const icons = new Map((hostsByGroup.group_meta ?? []).map((g) => [g.name, g.emoji]))
    const all: { name: string | null; emoji: string; hosts: Host[] }[] = [
      ...Object.entries(hostsByGroup.groups)
        .map(([name, hosts]) => ({ name, emoji: icons.get(name) ?? '', hosts })),
      { name: null, emoji: '', hosts: hostsByGroup.ungrouped_hosts },
    ]
    return all
      .filter((section) => groupFilter === null
        || (groupFilter === UNGROUPED ? section.name === null : section.name === groupFilter))
      .map((section) => ({ ...section, hosts: section.hosts.filter(matches) }))
      .filter((section) => section.hosts.length > 0)
  }, [hostsByGroup, matches, groupFilter])

  const visible = sections.reduce((n, s) => n + s.hosts.length, 0)
  const total = store.hosts.length

  const launch = async (host: Host) => {
    setLaunching((s) => ({ ...s, [host.name]: 'connecting' }))
    try {
      await withVault(() => api.connectHost(host.name))
      setLaunching((s) => ({ ...s, [host.name]: 'launched' }))
      window.setTimeout(() => setLaunching((s) => ({ ...s, [host.name]: undefined })), 1600)
    } catch (e) {
      setLaunching((s) => ({ ...s, [host.name]: undefined }))
      if (e instanceof Error && e.message !== 'Vault unlock cancelled') toast(e.message, 'error')
    }
  }

  const copy = async (text: string, label: string) => {
    if (await copyText(text)) toast(`${label} copied`, 'success')
    // Naming the value gives it somewhere to go even when every copy route is
    // blocked - it can at least be read off the screen
    else toast(`Copy blocked by the browser - ${text}`, 'error')
  }

  // A few pixels of travel before a press counts as a drag, so Launch and the
  // hover actions still take a plain click
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const reorderHosts = async (group: string, current: Host[], { active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const names = current.map((h) => h.name)
    const next = arrayMove(names, names.indexOf(String(active.id)), names.indexOf(String(over.id)))
    try {
      await api.setHostOrder(group, next)
      await reloadHosts()
    } catch {
      toast('Could not save the new order', 'error')
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    await api.deleteHost(deleting.name)
    toast(`'${deleting.name}' deleted`, 'success')
    setDeleting(null)
    await reloadHosts()
  }

  return (
    <>
      {/* toolbar */}
      <header className="flex shrink-0 flex-wrap items-center gap-2.5 border-b border-border bg-card/60 px-5 py-3 backdrop-blur">
        <div className="relative min-w-52 max-w-md flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="searchBox"
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search hosts or tags…"
            className="pl-9 pr-8"
          />
          {search && (
            <button
              type="button" aria-label="Clear search"
              onClick={() => setSearch('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:text-foreground cursor-pointer"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {tags.length > 0 && (
          <div className="relative">
            <Tag size={13} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <select
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="h-9 cursor-pointer appearance-none rounded-lg border border-input bg-card pl-8 pr-7 text-sm text-foreground focus:outline-none focus:border-ring"
            >
              <option value="">All tags</option>
              {tags.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        )}

        {groupFilter && (
          <Badge className="border-primary/40 bg-accent text-accent-foreground">
            <FolderOpen size={11} />
            {groupFilter === UNGROUPED ? 'Ungrouped' : `${groupIcon(hostsByGroup, groupFilter)}${groupFilter}`}
            <button type="button" aria-label="Clear group filter" onClick={clearGroupFilter} className="cursor-pointer hover:text-foreground">
              <X size={11} />
            </button>
          </Badge>
        )}

        <span className="ml-auto text-xs tabular-nums text-muted-foreground">
          {visible === total ? `${total} host${total === 1 ? '' : 's'}` : `${visible} of ${total} hosts`}
        </span>

        <div className="flex overflow-hidden rounded-lg border border-border">
          <button
            type="button" aria-label="Grid view"
            onClick={() => setView('grid')}
            className={cn('flex h-8 w-8 items-center justify-center cursor-pointer transition-colors',
              view === 'grid' ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted')}
          >
            <LayoutGrid size={15} />
          </button>
          <button
            type="button" aria-label="List view"
            onClick={() => setView('list')}
            className={cn('flex h-8 w-8 items-center justify-center cursor-pointer transition-colors',
              view === 'list' ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted')}
          >
            <List size={15} />
          </button>
        </div>

        <Button size="icon" variant="outline" aria-label="Refresh"
          onClick={() => reloadHosts().then(() => toast('Refreshed', 'success'))}>
          <RefreshCw size={14} />
        </Button>
        <Button size="icon" variant="outline" aria-label="Import hosts" onClick={() => setImporting(true)}>
          <Upload size={14} />
        </Button>
        <Button size="icon" variant="outline" aria-label="Export hosts" onClick={() => setExporting(true)}>
          <Download size={14} />
        </Button>
        <Button onClick={() => setEditing('new')}>
          <Plus size={15} /> Add host
        </Button>
      </header>

      {/* content */}
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {sections.length === 0 ? (
          <EmptyState
            filtered={total > 0}
            onAdd={() => setEditing('new')}
            onClear={() => { setSearch(''); setTagFilter(''); clearGroupFilter() }}
          />
        ) : (
          <div className="space-y-5">
            {/* Each group sits on its own surface. Spacing alone left one group
                running into the next on a tall listing - a panel gives the eye
                a boundary, and makes a group read as the single thing its tiles
                are dragged around inside. */}
            {sections.map((section) => (
              <section
                key={section.name ?? '·ungrouped'}
                className="animate-fade-up rounded-2xl border border-border bg-muted/40 p-4"
              >
                <div className="group/section mb-3 flex items-center gap-2">
                  {section.emoji && (
                    <span aria-hidden className="text-sm leading-none">{section.emoji}</span>
                  )}
                  <h2 className="text-[13px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {section.name ?? 'Ungrouped'}
                  </h2>
                  <span className="text-[11px] tabular-nums text-muted-foreground/70">{section.hosts.length}</span>
                  {/* Ungrouped is not a group - there is no name to change and
                      no icon to give it, so it gets no pencil. */}
                  {section.name && (
                    <Button
                      size="icon" variant="ghost"
                      aria-label={`Edit group ${section.name}`}
                      title="Rename or set an icon"
                      className="opacity-0 transition-opacity group-hover/section:opacity-100 focus-visible:opacity-100"
                      onClick={() => setEditingGroup({
                        name: section.name as string,
                        emoji: section.emoji,
                        count: section.hosts.length,
                      })}
                    >
                      <Pencil size={12} />
                    </Button>
                  )}
                </div>
                {/* Fixed column counts rather than auto-fill: auto-fill keeps
                    empty tracks at the end of a row, which is what left a 32in
                    monitor showing four narrow cards and a band of empty space.
                    These stretch to the width available, and stop at four so a
                    card never grows absurd. */}
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  // no `measuring` override here on purpose: the sortable
                  // strategy works out where each tile should sit by comparing
                  // the layout it started from against the order it would land
                  // in, so it needs the rects from before anything moved.
                  // Re-measuring every frame feeds it rects that already carry
                  // the shift, and the maths then settles on "stay put".
                  onDragStart={({ active }) =>
                    setDragged(section.hosts.find((h) => h.name === active.id) ?? null)}
                  onDragCancel={() => setDragged(null)}
                  onDragEnd={(event) => {
                    setDragged(null)
                    reorderHosts(section.name ?? '', section.hosts, event)
                  }}
                >
                  <SortableContext
                    items={section.hosts.map((h) => h.name)}
                    // tiles wrap in a grid and stack in a list, so the strategy
                    // has to match or the placeholders open in the wrong axis
                    strategy={view === 'grid' ? rectSortingStrategy : verticalListSortingStrategy}
                  >
                    <div className={cn(
                      view === 'grid'
                        ? 'grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4'
                        : 'space-y-2',
                      // while something is in flight the tiles are only scenery
                      // making room - they should not light up under the pointer
                      // or offer buttons. dnd-kit tracks the drag on the
                      // document and sorts by rects, so it is unaffected.
                      dragged && 'pointer-events-none',
                    )}>
                      {section.hosts.map((host) => (
                        <SortableHostTile
                          key={host.name}
                          host={host}
                          list={view === 'list'}
                          state={launching[host.name]}
                          onLaunch={() => launch(host)}
                          onEdit={() => setEditing(host)}
                          onDelete={() => setDeleting(host)}
                          onCopy={copy}
                        />
                      ))}
                    </div>
                  </SortableContext>
                  {/* Rendered under the pointer at full opacity while the tile
                      it came from fades to a placeholder. This is what makes a
                      drag feel like carrying the card rather than nudging it. */}
                  <DragOverlay dropAnimation={{ duration: 180, easing: 'cubic-bezier(0.2, 0, 0, 1)' }}>
                    {dragged && section.hosts.some((h) => h.name === dragged.name) ? (
                      <HostTile
                        host={dragged}
                        list={view === 'list'}
                        state={undefined}
                        onLaunch={() => {}}
                        onEdit={() => {}}
                        onDelete={() => {}}
                        onCopy={() => {}}
                        overlay
                      />
                    ) : null}
                  </DragOverlay>
                </DndContext>
              </section>
            ))}
          </div>
        )}
      </div>

      {editing !== null && (
        <HostDialog host={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete host?"
          body={<>Delete <strong>{deleting.name}</strong>? This cannot be undone. Its vault credential is not affected.</>}
          confirmLabel="Delete"
          destructive
          onConfirm={confirmDelete}
          onClose={() => setDeleting(null)}
        />
      )}
      {editingGroup && (
        <GroupDialog
          group={editingGroup.name}
          emoji={editingGroup.emoji}
          hostCount={editingGroup.count}
          onClose={() => setEditingGroup(null)}
        />
      )}
      {importing && <ImportDialog onClose={() => setImporting(false)} />}
      {exporting && <ExportDialog onClose={() => setExporting(false)} />}
    </>
  )
}

function EmptyState({ filtered, onAdd, onClear }: { filtered: boolean; onAdd: () => void; onClear: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center animate-fade-in">
      <div className="rounded-2xl bg-muted p-5 text-muted-foreground"><Terminal size={30} /></div>
      <div>
        <p className="font-semibold">{filtered ? 'No hosts match' : 'No hosts yet'}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {filtered ? 'Try clearing the search and filters.' : 'Add your first SSH host to get started.'}
        </p>
      </div>
      {filtered
        ? <Button variant="outline" onClick={onClear}>Clear filters</Button>
        : <Button onClick={onAdd}><Plus size={15} /> Add host</Button>}
    </div>
  )
}

interface TileProps {
  host: Host
  list: boolean
  state: LaunchState
  onLaunch: () => void
  onEdit: () => void
  onDelete: () => void
  onCopy: (text: string, label: string) => void
}

/** A host tile, made draggable within its own group.
 *
 * The listeners go on the card itself rather than a separate handle: the whole
 * tile is the thing you want to pick up. The sensor's activation distance is
 * what keeps Launch and the hover actions clickable - a press that never
 * travels is still a click.
 */
function SortableHostTile(props: TileProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: props.host.name })

  return (
    <HostTile
      {...props}
      tileRef={setNodeRef}
      dragging={isDragging}
      dragProps={{ ...attributes, ...listeners }}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 10 : undefined,
        position: isDragging ? 'relative' : undefined,
      }}
    />
  )
}

function HostTile({
  host, list, state, onLaunch, onEdit, onDelete, onCopy,
  tileRef, dragProps, dragging, style, overlay,
}: TileProps & {
  tileRef?: (el: HTMLElement | null) => void
  dragProps?: Record<string, unknown>
  dragging?: boolean
  style?: React.CSSProperties
  /** the copy carried under the pointer, rather than the one in the grid */
  overlay?: boolean
}) {
  const { credentials, vaultUnlocked } = useStore()
  const theme = themeById(host.theme)
  const credential = credentials.find((c) => c.name === host.credential)
  const login = effectiveLogin(host, credentials)
  const port = host.port && host.port !== 22 ? `:${host.port}` : ''
  const target = `${login ? `${login}@` : ''}${host.hostname}${port}`
  const address = `${host.hostname}${port}`
  const connectionString = `${login ? `${login}@` : ''}${host.hostname}`

  // How this host authenticates, as one mark. The name is worth knowing but not
  // worth a line of every tile, so it lives in the tooltip.
  const indicator = (() => {
    if (!host.credential) {
      return { icon: <TriangleAlert size={12} />, tone: 'border-destructive/40 text-destructive',
               tip: 'No credential - this host cannot connect yet' }
    }
    if (!vaultUnlocked || !credential) {
      return { icon: <KeyRound size={12} />, tone: '',
               tip: `${host.credential} - unlock the vault for details` }
    }
    return credential.type === 'key'
      ? { icon: <KeyRound size={12} />, tone: 'border-success/40 text-success',
          tip: `SSH key: ${credential.name}` }
      : { icon: <SquareAsterisk size={12} />, tone: 'border-warning/40 text-warning',
          tip: `Password: ${credential.name}` }
  })()

  const credentialBadge = (
    <Badge className={cn('px-1.5', indicator.tone)} title={indicator.tip} aria-label={indicator.tip}>
      {indicator.icon}
    </Badge>
  )

  // On a tile the actions float over the top-right corner rather than sitting
  // in the flow: four icon buttons would otherwise take half the card's width
  // away from the title and the endpoint, which are what people read.
  const actions = (
    <div className={cn(
      'flex items-center gap-1',
      !list && 'absolute right-2.5 top-2.5 z-10 rounded-lg border border-border bg-card/95 px-0.5 shadow-sm',
      !list && 'opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100',
    )}>
      <Button size="icon" variant="ghost" aria-label="Copy endpoint" title="Copy endpoint"
        onClick={() => onCopy(host.hostname, 'Endpoint')}><Copy size={13} /></Button>
      <Button size="icon" variant="ghost" aria-label="Copy connection string" title="Copy connection string"
        onClick={() => onCopy(connectionString, 'Connection string')}><Terminal size={13} /></Button>
      <Button size="icon" variant="ghost" aria-label="Edit host" title="Edit" onClick={onEdit}><Pencil size={13} /></Button>
      <Button size="icon" variant="ghost" aria-label="Delete host" title="Delete"
        className="hover:text-destructive" onClick={onDelete}><Trash2 size={13} /></Button>
    </div>
  )

  // mt-auto holds the button against the card's bottom edge, so a row of tiles
  // lines up however many tags each one wraps onto a second line
  const launchButton = (
    <Button
      variant="subtle"
      size={list ? 'sm' : 'md'}
      onClick={onLaunch}
      disabled={state === 'connecting'}
      className={cn(!list && 'mt-auto w-full', state === 'launched' && 'text-success')}
      style={{ ['--tint' as string]: theme.soft }}
    >
      {state === 'connecting' ? <Spinner /> : state === 'launched' ? <Check size={15} /> : <Rocket size={14} />}
      {state === 'connecting' ? 'Connecting…' : state === 'launched' ? 'Launched' : 'Launch'}
    </Button>
  )

  if (list) {
    return (
      <div
        ref={tileRef}
        {...dragProps}
        className={cn(
          'group flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5',
          'shadow-sm hover:shadow-md',
          // the overlay is mounted mid-drag, so the entry animation would play
          // again on the card the pointer has already picked up
          !overlay && 'animate-fade-up',
          // dnd-kit supplies its own transition inline while a drag is live;
          // ours would only be something for it to fight
          dragging ? 'transition-none' : 'transition-all duration-150',
          dragProps && 'cursor-grab active:cursor-grabbing touch-none select-none',
          // the card itself is drawn in the DragOverlay under the pointer, so
          // what stays behind is just the gap it will drop into - inert, or it
          // would still be painting its hover wash and action buttons
          dragging && 'opacity-40 pointer-events-none',
          // see the grid tile below - the carried row would otherwise hover itself
          overlay && 'cursor-grabbing pointer-events-none shadow-2xl',
        )}
        style={{ ...style, borderLeft: `3px solid ${theme.color}` }}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">
              {host.emoji && <span aria-hidden className="mr-1">{host.emoji}</span>}
              {host.name}
            </span>
            {credentialBadge}
          </div>
          <div className="truncate font-mono text-xs text-muted-foreground">{target}</div>
        </div>
        {(host.tags ?? []).slice(0, 3).map((t) => <Badge key={t}>{t}</Badge>)}
        {actions}
        {launchButton}
      </div>
    )
  }

  return (
    <div
      ref={tileRef}
      {...dragProps}
      className={cn(
        'group tile relative flex flex-col gap-2 overflow-hidden rounded-xl border border-border',
        'bg-card p-4 shadow-sm hover:shadow-lg',
        dragging ? 'transition-none' : 'transition-all duration-200',
        !overlay && 'animate-fade-up',
        // the lift on hover fights the drag transform, so only one at a time
        !dragging && 'hover:-translate-y-0.5',
        dragProps && 'cursor-grab active:cursor-grabbing touch-none select-none',
        dragging && 'opacity-40 pointer-events-none',
        // the carried card sits directly under the pointer, so without this it
        // hovers itself: theme wash on, action buttons out, on a card whose
        // buttons cannot be clicked mid-drag
        overlay && 'cursor-grabbing pointer-events-none',
      )}
      style={{
        ...style,
        // the lift has to go here rather than in a shadow-* class: the inset
        // rule below is the same property and would win
        boxShadow: overlay
          ? `inset 0 3px 0 0 ${theme.color}, 0 18px 38px -12px rgb(0 0 0 / 0.35)`
          : `inset 0 3px 0 0 ${theme.color}`,
        ['--tile-tint' as string]: theme.strong,
        ['--tile-tint-fade' as string]: theme.soft,
      }}
    >
      {actions}
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold" title={host.name}>
          {host.emoji && <span aria-hidden className="mr-1">{host.emoji}</span>}
          {host.name}
        </div>
        {/* the address on its own line - the login has its own below, so a long
            hostname gets the whole width before it has to ellipsise */}
        <div className="mt-0.5 truncate font-mono text-xs text-muted-foreground" title={address}>
          {address}
        </div>
      </div>
      <div className="min-w-0 truncate font-mono text-[11px] text-muted-foreground/80" title={login || undefined}>
        {login || <span className="not-italic text-destructive/80">no login</span>}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {credentialBadge}
        {(host.tags ?? []).map((t) => <Badge key={t}>{t}</Badge>)}
      </div>
      {launchButton}
    </div>
  )
}
