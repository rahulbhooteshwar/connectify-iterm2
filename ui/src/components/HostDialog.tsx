/** Add / edit host.
 *
 * Field naming is deliberate and measured, not cosmetic: WebKit's AutoFill
 * reads visible labels and element ids, and paints a contact card on anything
 * it takes for a person ("Name", id=hostName) and a house on a place
 * (id=hostAddress). "Title", "Endpoint" and "Login" - with ids to match -
 * came back clean in iTerm2's browser where the obvious words did not.
 * The stored fields are still name/hostname/username.
 */

import * as React from 'react'
import { ChevronRight, Plus, X } from 'lucide-react'
import { useStore } from '../store'
import * as api from '../lib/api'
import {
  DEFAULT_SSH_OPTIONS, LEGACY_PASSWORD_AUTH, PASSWORD_AUTH, SSH_OPTION_DEFS, type Host,
} from '../lib/types'
import { TILE_THEMES } from '../lib/themes'
import { Badge, Button, cn, Dialog, DialogBody, DialogContent, DialogFooter, Field, Input, Spinner } from './ui'
import { Combobox } from './Combobox'
import { CredentialDialog } from './CredentialDialog'

export function HostDialog({ host, onClose }: { host: Host | null; onClose: () => void }) {
  const { credentials, groups, profiles, toast, reloadHosts, reloadProfiles, reloadCredentials, withVault } = useStore()

  const [title, setTitle] = React.useState(host?.name ?? '')
  const [endpoint, setEndpoint] = React.useState(host?.hostname ?? '')
  const [login, setLogin] = React.useState(host?.username ?? '')
  const [port, setPort] = React.useState(String(host?.port ?? 22))
  const [credentialName, setCredentialName] = React.useState(host?.credential ?? '')
  const [profile, setProfile] = React.useState(host?.iterm_profile || 'Default')
  const [group, setGroup] = React.useState(host?.group ?? '')
  const [theme, setTheme] = React.useState(host?.theme || 'default')
  const [tags, setTags] = React.useState<string[]>(host?.tags ?? [])
  const [tagDraft, setTagDraft] = React.useState('')
  const [sshOptions, setSshOptions] = React.useState<string[]>(() => {
    const saved = host?.ssh_options
    const base = Array.isArray(saved) ? saved : DEFAULT_SSH_OPTIONS.password
    // Hosts saved before keyboard-interactive was allowed carry the old flag
    return base.map((o) => (o === LEGACY_PASSWORD_AUTH ? PASSWORD_AUTH : o))
  })
  const [verbosity, setVerbosity] = React.useState(host?.ssh_verbosity ?? 0)
  const [advancedOpen, setAdvancedOpen] = React.useState(false)
  const [newCredential, setNewCredential] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')

  const credential = credentials.find((c) => c.name === credentialName)
  const credentialLogin = (credential?.username ?? '').trim()

  const loginHint = credentialLogin
    ? login.trim()
      ? `'${credential!.name}' connects as ${credentialLogin} - that overrides ${login.trim()}.`
      : `'${credential!.name}' connects as ${credentialLogin}.`
    : login.trim()
      ? `Connects as ${login.trim()}.`
      : 'Required unless the credential supplies a login.'

  const profileKnown = !profile.trim()
    || profiles.some((p) => p.name.toLowerCase() === profile.trim().toLowerCase())

  const addTag = (raw: string) => {
    const value = raw.trim().replace(/,+$/, '')
    if (value && !tags.includes(value)) setTags((t) => [...t, value])
    setTagDraft('')
  }

  const onCredentialPicked = (name: string) => {
    setCredentialName(name)
    const picked = credentials.find((c) => c.name === name)
    if (picked) setSshOptions(DEFAULT_SSH_OPTIONS[picked.type])
  }

  const save = async () => {
    setError('')
    // One of the two has to name a login; when the vault is locked we cannot
    // tell what the credential carries, so leave that call to the server
    if (!login.trim() && credential && !credentialLogin) {
      setError(`Add a login - '${credential.name}' does not supply one`)
      return
    }
    setBusy(true)
    try {
      const payload = {
        name: title.trim(),
        hostname: endpoint.trim(),
        username: login.trim(),
        port: parseInt(port, 10) || 22,
        credential: credentialName,
        iterm_profile: profile.trim() || 'Default',
        group: group.trim(),
        theme,
        tags,
        ssh_options: sshOptions,
        ssh_verbosity: verbosity,
      }
      if (host) await api.updateHost(host.name, payload)
      else await api.createHost(payload)
      toast(host ? `'${payload.name}' saved` : `'${payload.name}' added`, 'success')
      await reloadHosts()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the host')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title={host ? 'Edit host' : 'Add host'} wide>
        <DialogBody className="space-y-4">
          <div className="grid grid-cols-[1fr_7rem] gap-3">
            <Field label="Title" htmlFor="hostTitle">
              <Input id="hostTitle" value={title} onChange={(e) => setTitle(e.target.value)}
                placeholder="Production DB" autoFocus />
            </Field>
            <Field label="Port" htmlFor="hostPort">
              <Input id="hostPort" type="number" value={port} min={1} max={65535}
                onChange={(e) => setPort(e.target.value)} />
            </Field>
          </div>

          <Field label="Endpoint" htmlFor="hostEndpoint">
            <Input id="hostEndpoint" value={endpoint} onChange={(e) => setEndpoint(e.target.value)}
              placeholder="db.internal.example.com or 10.0.0.42" />
          </Field>

          <Field label="Login" optional hint={loginHint} htmlFor="hostLogin">
            <Input id="hostLogin" value={login} onChange={(e) => setLogin(e.target.value)}
              placeholder="Leave empty to use the credential's login" />
          </Field>

          <Field label="Credential" htmlFor="hostCredential" hint={
            credential
              ? credential.type === 'key' ? `SSH key: ${credential.ssh_key_path || '(no path)'}` : 'Password credential'
              : credentialName ? 'This credential is not in the vault - add it or pick another.'
                : 'Pick a credential from the vault, or add a new one.'
          }>
            <div className="flex gap-2">
              <select
                id="hostCredential"
                value={credentialName}
                onChange={(e) => onCredentialPicked(e.target.value)}
                className="h-9 min-w-0 flex-1 cursor-pointer rounded-lg border border-input bg-card px-3 text-sm text-foreground focus:outline-none focus:border-ring"
              >
                <option value="">No credential</option>
                {credentials.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.type === 'key' ? 'SSH key' : 'password'})</option>
                ))}
                {credentialName && !credential && (
                  <option value={credentialName}>{credentialName} (missing from vault)</option>
                )}
              </select>
              <Button variant="outline" onClick={() => setNewCredential(true)}>
                <Plus size={14} /> New
              </Button>
            </div>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Group" optional htmlFor="hostGroup">
              <Combobox
                id="hostGroup"
                value={group}
                onChange={setGroup}
                options={groups.map((g) => ({ value: g }))}
                placeholder="Search or type a new group…"
                emptyText="New group - created on save"
              />
            </Field>
            <Field label="iTerm profile" htmlFor="itermProfile" hint={
              !profileKnown
                ? `'${profile}' is not in iTerm2 any more - the session will fall back to the default profile.`
                : `${profiles.length} profile(s) available`
            }>
              <Combobox
                id="itermProfile"
                value={profile}
                onChange={setProfile}
                options={profiles.map((p) => ({
                  value: p.name,
                  note: p.source === 'connectify' ? 'Connectify' : p.is_default ? 'default' : undefined,
                }))}
                onRefresh={reloadProfiles}
              />
            </Field>
          </div>

          <Field label="Tile theme">
            <div className="flex flex-wrap gap-2 pt-1">
              {TILE_THEMES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  title={t.label}
                  aria-label={`Theme ${t.label}`}
                  onClick={() => setTheme(t.id)}
                  className={cn(
                    'h-7 w-7 rounded-full transition-all duration-150 cursor-pointer hover:scale-110',
                    theme === t.id && 'ring-2 ring-ring ring-offset-2 ring-offset-card scale-110',
                  )}
                  style={{ background: t.color }}
                />
              ))}
            </div>
          </Field>

          <Field label="Tags" optional htmlFor="tagInput">
            <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-input bg-card px-2 py-1.5 focus-within:border-ring">
              {tags.map((t) => (
                <Badge key={t} className="bg-muted">
                  {t}
                  <button type="button" aria-label={`Remove tag ${t}`} className="cursor-pointer hover:text-foreground"
                    onClick={() => setTags(tags.filter((x) => x !== t))}>
                    <X size={10} />
                  </button>
                </Badge>
              ))}
              <input
                id="tagInput"
                value={tagDraft}
                placeholder={tags.length ? '' : 'Type and press Enter…'}
                autoComplete="off" autoCapitalize="off" autoCorrect="off" spellCheck={false}
                className="h-6 min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                onChange={(e) => setTagDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ' || e.key === ',') { e.preventDefault(); addTag(tagDraft) }
                  else if (e.key === 'Backspace' && !tagDraft && tags.length) setTags(tags.slice(0, -1))
                }}
                onBlur={() => tagDraft.trim() && addTag(tagDraft)}
              />
            </div>
          </Field>

          {/* advanced */}
          <div className="rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setAdvancedOpen((o) => !o)}
              className="flex w-full items-center gap-2 px-3.5 py-2.5 text-[13px] font-medium cursor-pointer"
            >
              <ChevronRight size={14} className={cn('transition-transform', advancedOpen && 'rotate-90')} />
              Advanced SSH options
              <span className="ml-auto text-xs font-normal text-muted-foreground">
                {sshOptions.length} selected{verbosity > 0 && ` · -${'v'.repeat(verbosity)} logs on`}
              </span>
            </button>
            {advancedOpen && (
              <div className="space-y-3 border-t border-border px-3.5 py-3 animate-fade-in">
                {SSH_OPTION_DEFS.map((def) => (
                  <label key={def.flag} className="flex cursor-pointer items-start gap-2.5">
                    <input
                      type="checkbox"
                      className="mt-0.5 accent-(--primary)"
                      checked={sshOptions.includes(def.flag)}
                      onChange={(e) => setSshOptions((current) =>
                        e.target.checked ? [...current, def.flag] : current.filter((f) => f !== def.flag))}
                    />
                    <span className="text-[13px] leading-tight">
                      {def.label}
                      <span className="block font-mono text-[11px] text-muted-foreground">-o {def.flag}</span>
                    </span>
                  </label>
                ))}
                <div className="flex items-center justify-between gap-3 border-t border-border pt-3">
                  <div className="text-[13px]">
                    Verbose logs
                    <span className="block text-[11px] text-muted-foreground">ssh's own debug output, printed in the session tab</span>
                  </div>
                  <div className="flex overflow-hidden rounded-lg border border-border">
                    {[0, 1, 2, 3].map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setVerbosity(level)}
                        className={cn('px-2.5 py-1 text-xs font-medium cursor-pointer transition-colors',
                          verbosity === level ? 'bg-primary text-primary-foreground' : 'hover:bg-muted')}
                      >
                        {level === 0 ? 'Off' : `-${'v'.repeat(level)}`}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {error && <p className="text-[13px] text-destructive">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy || !title.trim() || !endpoint.trim()}>
            {busy && <Spinner />} Save host
          </Button>
        </DialogFooter>
      </DialogContent>

      {newCredential && (
        <CredentialDialog
          credentialName={null}
          onClose={() => setNewCredential(false)}
          onSaved={async (name) => {
            setNewCredential(false)
            await withVault(reloadCredentials)
            onCredentialPicked(name)
          }}
        />
      )}
    </Dialog>
  )
}
