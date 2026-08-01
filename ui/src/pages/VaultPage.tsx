import * as React from 'react'
import { KeyRound, Lock, Pencil, Plus, RectangleEllipsis, Server, ShieldCheck, SquareAsterisk, Trash2, User } from 'lucide-react'
import { useStore } from '../store'
import * as api from '../lib/api'
import { ApiError } from '../lib/api'
import type { Credential } from '../lib/types'
import { Badge, Button, Dialog, DialogBody, DialogContent, DialogFooter, Field, SecretInput, Spinner } from '../components/ui'
import { CredentialDialog } from '../components/CredentialDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'

export function VaultPage() {
  const { credentials, vaultUnlocked, vaultExists, openGate, lockVault, toast, withVault, reloadCredentials } = useStore()

  const [editing, setEditing] = React.useState<string | null | 'new'>(null)
  const [showingHosts, setShowingHosts] = React.useState<Credential | null>(null)
  const [deleting, setDeleting] = React.useState<Credential | null>(null)
  const [inUse, setInUse] = React.useState<{ name: string; hosts: string[] } | null>(null)
  const [changingPasscode, setChangingPasscode] = React.useState(false)

  // The host form's duplicate-name dialog can hand over to "edit the existing
  // credential" from anywhere in the app
  React.useEffect(() => {
    const onEdit = (e: Event) => setEditing((e as CustomEvent<string>).detail)
    document.addEventListener('connectify:edit-credential', onEdit)
    return () => document.removeEventListener('connectify:edit-credential', onEdit)
  }, [])

  React.useEffect(() => {
    if (vaultUnlocked) withVault(reloadCredentials).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vaultUnlocked])

  const confirmDelete = async () => {
    if (!deleting) return
    try {
      await withVault(() => api.deleteCredential(deleting.name))
      toast(`'${deleting.name}' deleted`, 'success')
      setDeleting(null)
      await withVault(reloadCredentials)
    } catch (e) {
      setDeleting(null)
      if (e instanceof ApiError && (e.detail as any)?.code === 'credential_in_use') {
        setInUse({ name: deleting.name, hosts: (e.detail as any).hosts ?? [] })
      } else if (e instanceof Error && e.message !== 'Vault unlock cancelled') {
        toast(e.message, 'error')
      }
    }
  }

  return (
    <>
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-card/60 px-5 py-3 backdrop-blur">
        <div>
          <h1 className="text-[15px] font-bold tracking-tight">Credentials Vault</h1>
          <p className="text-xs text-muted-foreground">
            {credentials.length} credential{credentials.length === 1 ? '' : 's'} · encrypted in ~/.connectify/vault.json
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {vaultUnlocked && (
            <>
              <Button variant="outline" onClick={() => setChangingPasscode(true)}>
                <RectangleEllipsis size={14} /> Change passcode
              </Button>
              <Button variant="outline" onClick={lockVault}><Lock size={14} /> Lock</Button>
              <Button onClick={() => setEditing('new')}><Plus size={15} /> Add credential</Button>
            </>
          )}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {!vaultUnlocked ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center animate-fade-in">
            <div className="rounded-2xl bg-muted p-5 text-muted-foreground"><ShieldCheck size={30} /></div>
            <div>
              <p className="font-semibold">{vaultExists ? 'The vault is locked' : 'No vault yet'}</p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                {vaultExists
                  ? 'Unlock it to see and manage your credentials.'
                  : 'Create a vault to store SSH passwords and key passphrases, encrypted with a passcode only you know.'}
              </p>
            </div>
            <Button onClick={openGate}>{vaultExists ? 'Unlock vault' : 'Create vault'}</Button>
          </div>
        ) : credentials.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center animate-fade-in">
            <div className="rounded-2xl bg-muted p-5 text-muted-foreground"><KeyRound size={30} /></div>
            <div>
              <p className="font-semibold">No credentials yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Add one, then pick it on your hosts.</p>
            </div>
            <Button onClick={() => setEditing('new')}><Plus size={15} /> Add credential</Button>
          </div>
        ) : (
          <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(320px,1fr))]">
            {credentials.map((credential) => (
              <CredentialCard
                key={credential.name}
                credential={credential}
                onEdit={() => setEditing(credential.name)}
                onDelete={() => setDeleting(credential)}
                onShowHosts={() => setShowingHosts(credential)}
              />
            ))}
          </div>
        )}
      </div>

      {editing !== null && (
        <CredentialDialog
          credentialName={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      {showingHosts && (
        <ConfirmDialog
          title={`Hosts using '${showingHosts.name}'`}
          body={`${showingHosts.used_by.length} host${showingHosts.used_by.length === 1 ? '' : 's'} authenticate with this credential.`}
          hosts={showingHosts.used_by}
          onClose={() => setShowingHosts(null)}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete credential?"
          body={<>Delete <strong>{deleting.name}</strong> from the vault? This cannot be undone.</>}
          confirmLabel="Delete"
          destructive
          onConfirm={confirmDelete}
          onClose={() => setDeleting(null)}
        />
      )}
      {inUse && (
        <ConfirmDialog
          title="Still in use"
          body={<><strong>{inUse.name}</strong> cannot be deleted while these hosts use it. Point them at another credential first.</>}
          hosts={inUse.hosts}
          onClose={() => setInUse(null)}
        />
      )}
      {changingPasscode && <ChangePasscodeDialog onClose={() => setChangingPasscode(false)} />}
    </>
  )
}

function CredentialCard({ credential, onEdit, onDelete, onShowHosts }: {
  credential: Credential
  onEdit: () => void
  onDelete: () => void
  onShowHosts: () => void
}) {
  const usedBy = credential.used_by ?? []
  return (
    <div className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-sm transition-all duration-200 hover:shadow-md animate-fade-up">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate text-sm font-semibold">{credential.name}</span>
          {credential.type === 'key'
            ? <Badge className="border-success/40 text-success"><KeyRound size={10} /> SSH key</Badge>
            : <Badge className="border-warning/40 text-warning"><SquareAsterisk size={10} /> password</Badge>}
          {credential.username && (
            <Badge title="Overrides the login on hosts using this credential">
              <User size={10} /> {credential.username}
            </Badge>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
          <Button size="icon" variant="ghost" aria-label="Edit credential" onClick={onEdit}><Pencil size={13} /></Button>
          <Button size="icon" variant="ghost" aria-label="Delete credential" className="hover:text-destructive" onClick={onDelete}>
            <Trash2 size={13} />
          </Button>
        </div>
      </div>
      <div className="truncate text-xs text-muted-foreground">
        {credential.description || (credential.type === 'key' ? credential.ssh_key_path : 'Password stored')}
        {credential.type === 'key' && credential.has_passphrase && ' · passphrase set'}
      </div>
      <div>
        {usedBy.length > 0 ? (
          <button
            type="button"
            onClick={onShowHosts}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:border-ring hover:text-foreground"
          >
            <Server size={10} /> {usedBy.length} host{usedBy.length === 1 ? '' : 's'}
          </button>
        ) : (
          <span className="inline-flex items-center rounded-full border border-dashed border-border px-2.5 py-0.5 text-[11px] text-muted-foreground">
            Not used by any host
          </span>
        )}
      </div>
    </div>
  )
}

function ChangePasscodeDialog({ onClose }: { onClose: () => void }) {
  const { toast } = useStore()
  const [current, setCurrent] = React.useState('')
  const [next, setNext] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')

  const submit = async () => {
    if (next !== confirm) { setError('The new passcodes do not match'); return }
    setBusy(true)
    setError('')
    try {
      await api.vaultChangePasscode(current, next)
      toast('Passcode changed', 'success')
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change the passcode')
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title="Change passcode"
        description="Re-encrypts the vault. Every other open page is locked out and needs the new passcode.">
        <DialogBody className="space-y-4">
          <Field label="Current passcode">
            <SecretInput id="vaultPasscodeCurrent" value={current} onChange={setCurrent} autoFocus />
          </Field>
          <Field label="New passcode">
            <SecretInput id="vaultPasscodeNew" value={next} onChange={setNext} />
          </Field>
          <Field label="Confirm new passcode"
            hint="There is no recovery - if you forget this passcode the credentials are gone.">
            <SecretInput id="vaultPasscodeNewConfirm" value={confirm} onChange={setConfirm} />
          </Field>
          {error && <p className="text-[13px] text-destructive">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy || !current || !next || !confirm}>
            {busy && <Spinner />} Change passcode
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
