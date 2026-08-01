import * as React from 'react'
import { Search, Smile, X } from 'lucide-react'
import { EMOJI_CATEGORIES, searchEmoji } from '../lib/emoji'
import { Button, cn, Input, inputClass } from './ui'

/** The first grapheme of a string.
 *
 * An emoji is rarely one codepoint - a flag is two, a family with skin tones
 * can be seven - so slicing by character would leave a fragment that renders
 * as something else entirely. Intl.Segmenter knows where the boundaries are;
 * where it is missing, keeping the whole string is the safer failure (the
 * backend bounds the length anyway).
 */
function firstGrapheme(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const Segmenter = (Intl as { Segmenter?: typeof Intl.Segmenter }).Segmenter
  if (!Segmenter) return text
  const [first] = new Segmenter(undefined, { granularity: 'grapheme' }).segment(text)
  return first?.segment ?? text
}

/** Pick an icon: the system emoji picker, or a grid of common ones.
 *
 * macOS already has a complete emoji picker, and no web API can open it - but
 * it inserts into whatever text field has focus, so the field below is the
 * whole of it: focus it, press Control-Command-Space, pick anything macOS has.
 * The grid underneath is a shortcut for the ones a group is likely to want, so
 * the common case needs no shortcut at all.
 */
export function EmojiPicker({ value, onChange, id }: {
  value: string
  onChange: (emoji: string) => void
  id?: string
}) {
  const [term, setTerm] = React.useState('')
  const [category, setCategory] = React.useState(EMOJI_CATEGORIES[0].id)
  const field = React.useRef<HTMLInputElement>(null)

  const results = term.trim()
    ? searchEmoji(term)
    : (EMOJI_CATEGORIES.find((c) => c.id === category) ?? EMOJI_CATEGORIES[0]).emoji

  return (
    <div className="space-y-2">
      {/* the system picker inserts here */}
      <div className="flex items-center gap-2">
        <input
          ref={field}
          id={id}
          value={value}
          onChange={(e) => onChange(firstGrapheme(e.target.value))}
          placeholder="🙂"
          aria-label="Group icon"
          autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false}
          className={cn(inputClass, 'w-16 shrink-0 text-center text-lg leading-none')}
        />
        <p className="flex-1 text-xs leading-relaxed text-muted-foreground">
          Press <Shortcut>⌃</Shortcut> <Shortcut>⌘</Shortcut> <Shortcut>Space</Shortcut> in that
          field for macOS’s own emoji picker — or type, paste, or choose one below.
        </p>
        {value && (
          <Button size="sm" variant="ghost" onClick={() => onChange('')} title="Remove the icon">
            <X size={14} /> Clear
          </Button>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border p-2">
          <Smile size={15} className="ml-1 shrink-0 text-muted-foreground" />
          <div className="relative flex-1">
            <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Search common icons…"
              className="h-8 pl-8"
            />
          </div>
        </div>

        {!term.trim() && (
          <div className="flex gap-1 overflow-x-auto border-b border-border px-2 py-1.5">
            {EMOJI_CATEGORIES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setCategory(c.id)}
                className={cn(
                  'shrink-0 rounded-md px-2 py-1 text-[11px] font-medium cursor-pointer transition-colors',
                  c.id === category
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

        <div className="max-h-40 overflow-y-auto p-1.5">
          {results.length === 0 ? (
            <p className="px-2 py-5 text-center text-[13px] text-muted-foreground">
              Nothing common matches “{term.trim()}”. The system picker has everything else.
            </p>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(2rem,1fr))] gap-0.5">
              {results.map(([emoji, keywords]) => (
                <button
                  key={emoji}
                  type="button"
                  title={keywords.split(' ').slice(0, 3).join(', ')}
                  aria-label={keywords.split(' ')[0]}
                  aria-pressed={emoji === value}
                  onClick={() => onChange(emoji)}
                  className={cn(
                    'flex h-8 items-center justify-center rounded-md text-lg leading-none',
                    'cursor-pointer transition-colors hover:bg-muted',
                    emoji === value && 'bg-accent ring-1 ring-ring',
                  )}
                >
                  {emoji}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Shortcut({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-sans text-[10px] text-foreground">
      {children}
    </kbd>
  )
}
