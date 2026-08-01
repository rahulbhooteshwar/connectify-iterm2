/** Add / edit a vault credential. Loads the full record (with secrets) when
 * editing; omitted secrets are preserved server-side. Duplicate names come
 * back as a structured 409 and turn into the three-way choice dialog. */

import * as React from 'react'
import { useStore } from '../store'
import * as api from '../lib/api'
import { ApiError } from '../lib/api'
import { Button, Dialog, DialogBody, DialogContent, DialogFooter, Field, Input, SecretInput, Spinner } from './ui'

export function CredentialDialog({ credentialName, onClose, onSaved }: {
  credentialName: string | null
  onClose: () => void
  onSaved?: (name: string) => void | Promise<void>
}) {
  const { toast, withVault, reloadCredentials, reloadHosts } = useStore()

  const [loaded, setLoaded] = React.useState(credentialName === null)
  const [title, setTitle] = React.useState('')
  const [type, setType] = React.useState<'password' | 'key'>('password')
  const [loginName, setLoginName] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [keyPath, setKeyPath] = React.useState('')
  const [passphrase, setPassphrase] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [duplicate, setDuplicate] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!credentialName) return
    withVault(() => api.fetchCredential(credentialName)).then((c) => {
      setTitle(c.name)
      setType(c.type)
      setLoginName(c.username ?? '')
      setDescription(c.description ?? '')
      setPassword(c.password ?? '')
      setKeyPath(c.ssh_key_path ?? '')
      setPassphrase(c.passphrase ?? '')
      setLoaded(true)
    }).catch(() => { toast('Could not load that credential', 'error'); onClose() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [credentialName])

  const save = async () => {
    setBusy(true)
    setError('')
    const payload: Record<string, unknown> = {
      name: title.trim(), type, username: loginName.trim(), description: description.trim(),
    }
    if (type === 'password') payload.password = password
    else { payload.ssh_key_path = keyPath.trim(); payload.passphrase = passphrase }

    try {
      const result = await withVault(() =>
        credentialName ? api.updateCredential(credentialName, payload) : api.createCredential(payload))
      toast((result as { message?: string }).message ?? 'Credential saved', 'success')
      await withVault(reloadCredentials)
      if ((result as { renamed_hosts?: number }).renamed_hosts) await reloadHosts()
      await onSaved?.(title.trim())
      onClose()
    } catch (e) {
      if (e instanceof ApiError && (e.detail as any)?.code === 'duplicate_name') {
        setDuplicate((e.detail as any).name)
      } else if (e instanceof Error && e.message !== 'Vault unlock cancelled') {
        setError(e.message)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title={credentialName ? 'Edit credential' : 'Add credential'} wide>
        {!loaded ? (
          <DialogBody className="flex items-center justify-center py-10"><Spinner /></DialogBody>
        ) : (
          <>
            <DialogBody className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Title">
                  <Input id="credentialTitle" value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="prod-admin" autoFocus={!credentialName} />
                </Field>
                <Field label="Type">
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value as 'password' | 'key')}
                    className="h-9 w-full cursor-pointer rounded-lg border border-input bg-card px-3 text-sm text-foreground focus:outline-none focus:border-ring"
                  >
                    <option value="password">Password</option>
                    <option value="key">SSH key</option>
                  </select>
                </Field>
              </div>

              <Field label="Login" optional
                hint="Overrides the login on every host that uses this credential.">
                <Input id="credentialLogin" value={loginName} onChange={(e) => setLoginName(e.target.value)}
                  placeholder="ubuntu" />
              </Field>

              <Field label="Description" optional>
                <Input id="credentialDescription" value={description} onChange={(e) => setDescription(e.target.value)}
                  placeholder="Shared admin login for production" />
              </Field>

              {type === 'password' ? (
                <Field label="Password">
                  <SecretInput id="credentialPassword" value={password} onChange={setPassword} />
                </Field>
              ) : (
                <>
                  <Field label="SSH key path">
                    <Input id="credentialKeyPath" value={keyPath} onChange={(e) => setKeyPath(e.target.value)}
                      placeholder="~/.ssh/id_ed25519" />
                  </Field>
                  <Field label="Passphrase" optional>
                    <SecretInput id="credentialPassphrase" value={passphrase} onChange={setPassphrase} />
                  </Field>
                </>
              )}

              {error && <p className="text-[13px] text-destructive">{error}</p>}
            </DialogBody>
            <DialogFooter>
              <Button variant="ghost" onClick={onClose}>Cancel</Button>
              <Button onClick={save} disabled={busy || !title.trim() || (type === 'key' && !keyPath.trim())}>
                {busy && <Spinner />} Save credential
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>

      {duplicate && (
        <DuplicateNameDialog
          name={duplicate}
          onClose={() => setDuplicate(null)}
          onEditExisting={() => {
            // Reopen this dialog against the existing credential instead
            setDuplicate(null)
            onClose()
            window.setTimeout(() => document.dispatchEvent(
              new CustomEvent('connectify:edit-credential', { detail: duplicate })), 0)
          }}
        />
      )}
    </Dialog>
  )
}

function DuplicateNameDialog({ name, onClose, onEditExisting }: {
  name: string
  onClose: () => void
  onEditExisting: () => void
}) {
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent
        title="That name is taken"
        description={<>A credential called <strong>{name}</strong> already exists. What would you like to do?</>}
      >
        <DialogBody className="space-y-2">
          <Button variant="outline" className="w-full justify-start" onClick={onClose}>
            Choose a different name
          </Button>
          <Button variant="outline" className="w-full justify-start" onClick={onEditExisting}>
            Edit the existing credential instead
          </Button>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
