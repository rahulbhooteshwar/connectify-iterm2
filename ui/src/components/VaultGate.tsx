/** The unlock / create dialog. Shown as soon as the app opens (the vault is
 * locked whenever the page loads, by design) and again whenever an operation
 * hits a locked vault - withVault() parks the operation until this resolves. */

import * as React from 'react'
import { ShieldCheck } from 'lucide-react'
import { useStore } from '../store'
import { Button, Dialog, DialogBody, DialogContent, DialogFooter, Field, SecretInput, Spinner } from './ui'

export function VaultGate() {
  const { gateOpen, closeGate, vaultExists, submitPasscode } = useStore()
  const [passcode, setPasscode] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [error, setError] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const creating = !vaultExists

  React.useEffect(() => {
    if (gateOpen) { setPasscode(''); setConfirm(''); setError('') }
  }, [gateOpen])

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      await submitPasscode(passcode, confirm)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Wrong passcode')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={gateOpen} onOpenChange={(open) => { if (!open) closeGate() }}>
      <DialogContent
        title={creating ? 'Create your vault' : 'Unlock the vault'}
        description={creating
          ? 'Choose a passcode. It encrypts every credential you store and is never saved anywhere.'
          : 'Your credentials are encrypted at rest. Enter the passcode to work with them.'}
      >
        <form onSubmit={submit}>
          <DialogBody className="space-y-4">
            <div className="flex justify-center pb-1 pt-2">
              <div className="rounded-2xl bg-accent p-4 text-accent-foreground">
                <ShieldCheck size={28} />
              </div>
            </div>
            <Field label="Passcode">
              <SecretInput id="vaultPasscode" value={passcode} onChange={setPasscode} autoFocus />
            </Field>
            {creating && (
              <Field
                label="Confirm passcode"
                hint="There is no recovery - if you forget this passcode the credentials are gone."
              >
                <SecretInput id="vaultPasscodeConfirm" value={confirm} onChange={setConfirm} />
              </Field>
            )}
            {error && <p className="text-[13px] text-destructive">{error}</p>}
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={closeGate}>Not now</Button>
            <Button
              type="submit"
              onClick={() => submit()}
              disabled={busy || !passcode || (creating && !confirm)}
            >
              {busy && <Spinner />}
              {creating ? 'Create vault' : 'Unlock'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
