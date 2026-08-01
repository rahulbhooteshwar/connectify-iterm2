/** The small shadcn-style primitives everything is built from. */

import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X, Eye, EyeOff, Loader2 } from 'lucide-react'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// --- Button ------------------------------------------------------------------

const buttonVariants = {
  default: 'bg-primary text-primary-foreground hover:opacity-90',
  outline: 'border border-border bg-transparent hover:bg-muted text-foreground',
  ghost: 'hover:bg-muted text-foreground',
  destructive: 'bg-destructive text-white hover:opacity-90',
  subtle: 'bg-muted text-foreground hover:bg-accent',
}

export function Button({
  variant = 'default', size = 'md', className, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof buttonVariants
  size?: 'sm' | 'md' | 'icon'
}) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium',
        'transition-all duration-150 active:scale-[0.98] cursor-pointer',
        'focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2',
        'disabled:opacity-50 disabled:pointer-events-none',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-9 px-4 text-sm',
        size === 'icon' && 'h-8 w-8 text-sm',
        buttonVariants[variant],
        className,
      )}
      {...props}
    />
  )
}

// --- Inputs ------------------------------------------------------------------

export const inputClass = cn(
  'h-9 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground',
  'placeholder:text-muted-foreground transition-colors',
  'focus:outline-none focus:border-ring focus:ring-2 focus:ring-ring/25',
)

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        className={cn(inputClass, className)}
        {...props}
      />
    )
  },
)

export function Field({ label, hint, optional, children }: {
  label: string
  hint?: React.ReactNode
  optional?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[13px] font-medium text-foreground">
        {label}
        {optional && <span className="ml-1 font-normal text-muted-foreground">(optional)</span>}
      </span>
      {children}
      {hint && <span className="block text-xs leading-relaxed text-muted-foreground">{hint}</span>}
    </label>
  )
}

/** A masked secret field.
 *
 * Starts as type=password AND carries the CSS mask, so it is masked from the
 * first paint twice over. Where the browser can mask a text field itself
 * (-webkit-text-security) it is swapped to text, which removes the input
 * WebKit's AutoFill key attaches to. The eye toggles either mechanism.
 */
export function SecretInput({ value, onChange, id, placeholder, autoFocus }: {
  value: string
  onChange: (value: string) => void
  id?: string
  placeholder?: string
  autoFocus?: boolean
}) {
  const [revealed, setRevealed] = React.useState(false)
  const cssMasking = React.useMemo(
    () => typeof CSS !== 'undefined' && CSS.supports?.('-webkit-text-security', 'disc'),
    [],
  )
  const type = revealed ? 'text' : cssMasking ? 'text' : 'password'

  return (
    <div className="relative">
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        data-lpignore="true"
        data-1p-ignore="true"
        className={cn(inputClass, 'masked-input pr-10', revealed && 'is-revealed')}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label={revealed ? 'Hide' : 'Reveal'}
        onClick={() => setRevealed((r) => !r)}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
      >
        {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
    </div>
  )
}

// --- Badge -------------------------------------------------------------------

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5',
        'text-[11px] font-medium text-muted-foreground',
        className,
      )}
      {...props}
    />
  )
}

// --- Spinner -----------------------------------------------------------------

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('animate-[spin_0.8s_linear_infinite]', className)} size={16} />
}

// --- Dialog (Radix, shadcn-style) -------------------------------------------

export function Dialog({ open, onOpenChange, children }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      {children}
    </DialogPrimitive.Root>
  )
}

export function DialogContent({ title, description, wide, dismissable = true, children }: {
  title: string
  description?: React.ReactNode
  wide?: boolean
  dismissable?: boolean
  children: React.ReactNode
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[2px] animate-fade-in" />
      <DialogPrimitive.Content
        onInteractOutside={(e) => { if (!dismissable) e.preventDefault() }}
        onEscapeKeyDown={(e) => {
          if (!dismissable) { e.preventDefault(); return }
          // Radix listens for Escape on the document in the capture phase, so a
          // dropdown inside the dialog cannot stop it from getting here. If one
          // is open, Escape belongs to it - closing the dialog would throw away
          // a half-filled form because someone dismissed a suggestion list.
          if (document.querySelector('[data-popup-open="true"]')) e.preventDefault()
        }}
        aria-describedby={undefined}
        className={cn(
          'fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 animate-zoom-in',
          'flex max-h-[85vh] w-[calc(100vw-2rem)] flex-col rounded-xl border border-border',
          'bg-card text-card-foreground shadow-2xl',
          wide ? 'max-w-2xl' : 'max-w-md',
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div>
            <DialogPrimitive.Title className="text-base font-semibold">{title}</DialogPrimitive.Title>
            {description && <p className="mt-1 text-[13px] text-muted-foreground">{description}</p>}
          </div>
          {dismissable && (
            <DialogPrimitive.Close
              aria-label="Close"
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground cursor-pointer"
            >
              <X size={16} />
            </DialogPrimitive.Close>
          )}
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

/** Scrolling body + pinned footer: dialogs cap at 85vh and the actions stay
 * reachable however long the form grows. */
export function DialogBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('flex-1 overflow-y-auto px-6 py-4', className)}>{children}</div>
}

export function DialogFooter({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
      {children}
    </div>
  )
}
