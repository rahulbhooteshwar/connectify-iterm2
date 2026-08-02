import * as React from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useStore } from '../store'
import { cn, Spinner } from './ui'

// emoji-mart plus its ~200KB dataset only costs bandwidth when someone opens
// the picker, not on every page load - dynamic import splits it into its own
// chunk instead of bloating the bundle everyone downloads to see a host list.
const LazyPicker = React.lazy(async () => {
  const [{ default: Picker }, { default: data }] = await Promise.all([
    import('@emoji-mart/react'),
    import('@emoji-mart/data'),
  ])
  return {
    default: (props: { onEmojiSelect: (emoji: { native: string }) => void; theme: 'dark' | 'light' }) => (
      <Picker
        data={data}
        onEmojiSelect={props.onEmojiSelect}
        set="native"
        theme={props.theme}
        previewPosition="none"
        skinTonePosition="search"
        maxFrequentRows={2}
        perLine={8}
      />
    ),
  }
})

/** The picker's own stylesheet hard-codes `height: 435px` on its host element,
 * which is taller than the space under a field in an 85vh dialog. These bound
 * it to what is actually free, and the width is what perLine={8} produces. */
const PICKER_WIDTH = 348
const PICKER_MAX_HEIGHT = 420
const PICKER_MIN_HEIGHT = 240
const GAP = 6
const MARGIN = 8

interface Position {
  left: number
  top: number
  height: number
  /** fixed when anchored to the viewport, absolute when inside a dialog */
  fixed: boolean
}

/** Where the popover fits: under the trigger if there is room, above it if not,
 * clamped to the viewport either way and never taller than the space it has.
 *
 * The result is in viewport coordinates, then rebased onto `container` when
 * that is a positioned element. This matters because the dialog is centred
 * with a CSS transform, and a transformed ancestor becomes the containing
 * block for `position: fixed` descendants - "fixed" inside one means fixed to
 * *it*, not to the window, so viewport numbers would land the panel somewhere
 * else entirely.
 */
function place(trigger: DOMRect, container: HTMLElement): Position {
  const below = window.innerHeight - trigger.bottom - GAP - MARGIN
  const above = trigger.top - GAP - MARGIN
  const openUp = below < PICKER_MIN_HEIGHT && above > below

  const room = openUp ? above : below
  const height = Math.max(PICKER_MIN_HEIGHT, Math.min(PICKER_MAX_HEIGHT, room))

  const left = Math.max(MARGIN, Math.min(trigger.left, window.innerWidth - PICKER_WIDTH - MARGIN))
  const top = openUp ? Math.max(MARGIN, trigger.top - GAP - height) : trigger.bottom + GAP

  if (container === document.body) return { left, top, height, fixed: true }

  const origin = container.getBoundingClientRect()
  return { left: left - origin.left, top: top - origin.top, height, fixed: false }
}

/** Pick an optional icon, for a host or a group.
 *
 * emoji-mart, not a hand-rolled grid: full search, categories, skin tones,
 * recents - the things a real picker needs that are not worth rebuilding.
 * `set="native"` is what keeps it offline - every other set renders `<img>`
 * tags pointed at a CDN, but native renders the Unicode character itself
 * through a `<span>`, so nothing is ever fetched. `data` is imported directly
 * from @emoji-mart/data rather than left to its default (a fetch call), which
 * bundles the ~200KB dataset instead of reaching the network for it.
 *
 * The panel is portalled and positioned in viewport coordinates. Rendered in
 * place it was clipped by the dialog body's own scroll container, which is
 * what `overflow-y: auto` does to any child that overflows it - no z-index
 * can lift a box out of an ancestor that clips it.
 */
export function EmojiMartPicker({ value, onChange, id, label = 'icon' }: {
  value: string
  onChange: (emoji: string) => void
  id?: string
  label?: string
}) {
  const { dark } = useStore()
  const [open, setOpen] = React.useState(false)
  const [position, setPosition] = React.useState<Position | null>(null)
  const triggerRef = React.useRef<HTMLButtonElement>(null)
  const panelRef = React.useRef<HTMLDivElement>(null)
  const scrollerRef = React.useRef<HTMLElement | null>(null)

  // Portal into the dialog rather than the body when there is one: Radix traps
  // focus inside its content, and a panel outside that tree would have focus
  // pulled back out of the search field on every keystroke.
  const container = React.useMemo(() => {
    if (!open) return null
    return triggerRef.current?.closest('[role="dialog"]') ?? document.body
  }, [open])

  const reposition = React.useCallback(() => {
    const trigger = triggerRef.current?.getBoundingClientRect()
    const host = triggerRef.current?.closest('[role="dialog"]') ?? document.body
    if (trigger) setPosition(place(trigger, host as HTMLElement))
  }, [])

  React.useEffect(() => {
    if (!open) return
    reposition()

    const onDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (!panelRef.current?.contains(target) && !triggerRef.current?.contains(target)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    // The trigger scrolls with the dialog body, so the panel has to follow it
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [open, reposition])

  // The emoji list scrolls inside the picker's shadow root, and a wheel event
  // crossing that boundary is retargeted to the host element. The dialog's
  // scroll lock therefore sees a wheel over an `em-emoji-picker` with no
  // scrollable ancestor it can find, assumes the page behind would scroll, and
  // cancels the event - so the list never moves. It scrolls perfectly well when
  // driven directly, so that is what this does.
  React.useEffect(() => {
    const panel = panelRef.current
    if (!open || !panel) return
    scrollerRef.current = null

    const findScroller = () => {
      const shadow = panel.querySelector('em-emoji-picker')?.shadowRoot
      if (!shadow) return null
      // emoji-mart's own class for it, with a search by behaviour as a fallback
      // so a renamed class degrades to slower rather than broken
      return shadow.querySelector<HTMLElement>('.scroll')
        ?? [...shadow.querySelectorAll<HTMLElement>('*')].find(
          (el) => el.scrollHeight > el.clientHeight
            && /auto|scroll/.test(getComputedStyle(el).overflowY),
        ) ?? null
    }

    const onWheel = (event: WheelEvent) => {
      if (!scrollerRef.current?.isConnected) scrollerRef.current = findScroller()
      const scroller = scrollerRef.current
      if (!scroller) return
      scroller.scrollTop += event.deltaY
      // we are the only one scrolling anything here
      event.preventDefault()
    }

    panel.addEventListener('wheel', onWheel, { passive: false })
    return () => panel.removeEventListener('wheel', onWheel)
    // `position` is in here because the panel only mounts once it is placed
  }, [open, position])

  return (
    // data-popup-open tells an enclosing dialog that Escape is spoken for -
    // see DialogContent's onEscapeKeyDown
    <div className="relative inline-block" data-popup-open={open ? 'true' : undefined}>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={value ? `Change the ${label}` : `Choose an ${label}`}
        aria-expanded={open}
        className={cn(
          'flex h-9 w-9 items-center justify-center rounded-lg border border-input bg-card text-lg leading-none',
          'cursor-pointer transition-colors hover:border-ring',
        )}
      >
        {value || <span className="text-muted-foreground">🙂</span>}
      </button>
      {value && (
        <button
          type="button"
          aria-label={`Remove the ${label}`}
          title="Remove"
          onClick={(e) => { e.stopPropagation(); onChange('') }}
          className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
        >
          <X size={10} />
        </button>
      )}

      {open && position && container && createPortal(
        <div
          ref={panelRef}
          // above the dialog (z-50) and the toasts (z-70); the tooltip at z-80
          // never coexists with an open picker
          className={cn(
            'emoji-popover z-[90] animate-zoom-in overflow-hidden rounded-xl border border-border shadow-2xl',
            position.fixed ? 'fixed' : 'absolute',
          )}
          style={{
            left: position.left,
            top: position.top,
            width: PICKER_WIDTH,
            height: position.height,
            // handed to the picker's host element, which otherwise insists on 435px
            ['--emoji-picker-height' as string]: `${position.height}px`,
          }}
        >
          <React.Suspense fallback={
            <div className="flex h-full w-full items-center justify-center bg-card"><Spinner /></div>
          }>
            <LazyPicker
              onEmojiSelect={(emoji) => { onChange(emoji.native); setOpen(false) }}
              theme={dark ? 'dark' : 'light'}
            />
          </React.Suspense>
        </div>,
        container,
      )}
    </div>
  )
}
