import * as React from 'react'
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

/** Pick an optional icon, for a host or a group.
 *
 * emoji-mart, not a hand-rolled grid: full search, categories, skin tones,
 * recents - the things a real picker needs that are not worth rebuilding.
 * `set="native"` is what keeps it offline - every other set renders `<img>`
 * tags pointed at a CDN, but native renders the Unicode character itself
 * through a `<span>`, so nothing is ever fetched. `data` is imported directly
 * from @emoji-mart/data rather than left to its default (a fetch call), which
 * bundles the ~200KB dataset instead of reaching the network for it.
 */
export function EmojiMartPicker({ value, onChange, id, label = 'icon' }: {
  value: string
  onChange: (emoji: string) => void
  id?: string
  label?: string
}) {
  const { dark } = useStore()
  const [open, setOpen] = React.useState(false)
  const rootRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    // data-popup-open tells an enclosing dialog that Escape is spoken for -
    // see DialogContent's onEscapeKeyDown
    <div ref={rootRef} className="relative inline-block" data-popup-open={open ? 'true' : undefined}>
      <button
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

      {open && (
        <div className="absolute left-0 top-[calc(100%+6px)] z-50 animate-zoom-in overflow-hidden rounded-xl border border-border shadow-2xl">
          <React.Suspense fallback={<div className="flex h-80 w-80 items-center justify-center"><Spinner /></div>}>
            <LazyPicker
              onEmojiSelect={(emoji) => { onChange(emoji.native); setOpen(false) }}
              theme={dark ? 'dark' : 'light'}
            />
          </React.Suspense>
        </div>
      )}
    </div>
  )
}
