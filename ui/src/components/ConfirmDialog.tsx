/** A generic confirm, plus the credential-specific variants built on it. */

import * as React from 'react'
import { TriangleAlert } from 'lucide-react'
import { Button, Dialog, DialogBody, DialogContent, DialogFooter, Spinner } from './ui'

export function ConfirmDialog({ title, body, confirmLabel, destructive, onConfirm, onClose, hosts }: {
  title: string
  body: React.ReactNode
  confirmLabel?: string
  destructive?: boolean
  /** omit to make it informational (Close only) */
  onConfirm?: () => void | Promise<void>
  onClose: () => void
  /** optional host-name list, e.g. "these hosts still use it" */
  hosts?: string[]
}) {
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')

  const confirm = async () => {
    if (!onConfirm) return
    setBusy(true)
    setError('')
    try {
      await onConfirm()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title={title}>
        <DialogBody className="space-y-3">
          <div className="flex gap-3">
            {destructive && <TriangleAlert size={20} className="mt-0.5 shrink-0 text-destructive" />}
            <p className="text-sm leading-relaxed text-muted-foreground">{body}</p>
          </div>
          {hosts && hosts.length > 0 && (
            <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg bg-muted px-4 py-3 text-sm">
              {[...hosts].sort((a, b) => a.localeCompare(b)).map((h) => (
                <li key={h} className="list-inside list-disc">{h}</li>
              ))}
            </ul>
          )}
          {error && <p className="text-[13px] text-destructive">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>{onConfirm ? 'Cancel' : 'Close'}</Button>
          {onConfirm && (
            <Button variant={destructive ? 'destructive' : 'default'} onClick={confirm} disabled={busy}>
              {busy && <Spinner />} {confirmLabel ?? 'Confirm'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
