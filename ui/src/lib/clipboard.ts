/** Copy text, by whichever route the browser will actually allow.
 *
 * The async Clipboard API is the right one, and it is also the one that
 * refuses most often: it needs a secure context (so it is simply absent when
 * the UI is reached over the LAN with --share), and WebKit rejects it with
 * "Document is not focused" whenever the page is not the focused document -
 * which, embedded in an iTerm2 tab beside a terminal, it frequently is not.
 * That is the "works sometimes, fails mostly" case.
 *
 * execCommand('copy') is deprecated but has neither restriction: it acts on a
 * selection synchronously, inside the click that triggered it. So it is the
 * fallback, and between the two something almost always gets through.
 */
export async function copyText(text: string): Promise<boolean> {
  if (!text) return false

  // Asking for focus first is enough to satisfy WebKit in some of the cases
  // where it would otherwise reject the write outright
  try { window.focus() } catch { /* not fatal */ }

  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // fall through - the legacy path has a real chance where this failed
    }
  }

  return legacyCopy(text)
}

/** Select text in an offscreen field and let the browser copy the selection. */
function legacyCopy(text: string): boolean {
  const field = document.createElement('textarea')
  field.value = text
  field.setAttribute('readonly', '')
  // Fixed and transparent rather than display:none - a hidden field cannot be
  // selected, and anything in the layout flow would scroll the page
  field.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none'

  document.body.appendChild(field)
  const previous = document.activeElement as HTMLElement | null

  try {
    field.focus({ preventScroll: true })
    field.select()
    field.setSelectionRange(0, text.length)   // iOS needs the explicit range
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    document.body.removeChild(field)
    previous?.focus?.()
  }
}
