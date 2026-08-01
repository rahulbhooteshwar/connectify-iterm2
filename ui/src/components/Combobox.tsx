/** A searchable dropdown over free text - the group and iTerm profile fields.
 * Types into the input filter the options; the typed text itself stays valid,
 * because both fields accept values the list does not know about. */

import * as React from 'react'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { cn, inputClass } from './ui'

export interface ComboOption {
  value: string
  note?: string
}

export function Combobox({ id, value, onChange, options, placeholder, onRefresh, emptyText }: {
  id?: string
  value: string
  onChange: (value: string) => void
  options: ComboOption[]
  placeholder?: string
  onRefresh?: () => void | Promise<void>
  emptyText?: string
}) {
  const [open, setOpen] = React.useState(false)
  const [highlight, setHighlight] = React.useState(-1)
  const rootRef = React.useRef<HTMLDivElement>(null)
  const listRef = React.useRef<HTMLDivElement>(null)

  const term = value.trim().toLowerCase()
  const filtered = term
    ? options.filter((o) => o.value.toLowerCase().includes(term))
    : options

  React.useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  React.useEffect(() => {
    if (highlight >= 0) {
      listRef.current?.children[highlight]?.scrollIntoView({ block: 'nearest' })
    }
  }, [highlight])

  const pick = (v: string) => { onChange(v); setOpen(false); setHighlight(-1) }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!open) { setOpen(true); return }
      const delta = e.key === 'ArrowDown' ? 1 : -1
      setHighlight((h) => (h + delta + filtered.length) % Math.max(filtered.length, 1))
    } else if (e.key === 'Enter') {
      if (open && highlight >= 0 && filtered[highlight]) {
        e.preventDefault()
        pick(filtered[highlight].value)
      } else {
        setOpen(false)
      }
    } else if (e.key === 'Escape') {
      // Escape dismisses the list, and only the list: letting it through would
      // reach the dialog behind and throw away everything the user has typed
      if (open) e.stopPropagation()
      setOpen(false)
      setHighlight(-1)
    }
  }

  return (
    // data-popup-open tells an enclosing dialog that Escape is spoken for
    <div ref={rootRef} className="relative" data-popup-open={open ? 'true' : undefined}>
      <input
        id={id}
        type="text"
        value={value}
        placeholder={placeholder}
        autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false}
        className={cn(inputClass, onRefresh ? 'pr-16' : 'pr-9')}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setHighlight(-1) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
        {onRefresh && (
          <button
            type="button" tabIndex={-1} aria-label="Refresh options" title="Refresh"
            onClick={() => onRefresh()}
            className="rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
          >
            <RefreshCw size={13} />
          </button>
        )}
        <button
          type="button" tabIndex={-1} aria-label="Show options"
          onClick={() => setOpen((o) => !o)}
          className="rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
        >
          <ChevronDown size={14} className={cn('transition-transform', open && 'rotate-180')} />
        </button>
      </div>

      {open && (
        <div
          ref={listRef}
          className="absolute inset-x-0 top-full z-30 mt-1 max-h-44 overflow-y-auto overscroll-contain rounded-lg border border-border bg-card py-1 shadow-xl animate-fade-in"
        >
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              {emptyText ?? 'Nothing matches - the typed value is used as-is'}
            </div>
          ) : filtered.map((option, index) => (
            <button
              key={option.value}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); pick(option.value) }}
              className={cn(
                'flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm cursor-pointer',
                index === highlight ? 'bg-accent text-accent-foreground' : 'hover:bg-muted',
                option.value === value && 'font-semibold',
              )}
            >
              <span className="truncate">{option.value}</span>
              {option.note && <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">{option.note}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
