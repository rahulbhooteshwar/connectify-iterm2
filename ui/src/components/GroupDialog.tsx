import * as React from 'react'
import { useStore } from '../store'
import * as api from '../lib/api'
import { ApiError } from '../lib/api'
import { Button, Dialog, DialogBody, DialogContent, DialogFooter, Field, Input } from './ui'
import { EmojiMartPicker } from './EmojiMartPicker'

/** Rename a group, and give it an icon.
 *
 * A group is only a label repeated across its hosts, so renaming one rewrites
 * every host that carries it - the dialog says how many that will be, because
 * "rename" reading as "edit one thing" would understate it.
 */
export function GroupDialog({ group, emoji: initialEmoji, hostCount, onClose }: {
  group: string
  emoji: string
  hostCount: number
  onClose: () => void
}) {
  const { reloadHosts, toast } = useStore()
  const [name, setName] = React.useState(group)
  const [emoji, setEmoji] = React.useState(initialEmoji)
  const [error, setError] = React.useState('')
  const [saving, setSaving] = React.useState(false)

  const trimmed = name.trim()
  const renaming = trimmed !== group
  const dirty = renaming || emoji !== initialEmoji

  const save = async () => {
    if (!trimmed) { setError('A group needs a name.'); return }
    setSaving(true)
    setError('')
    try {
      const result = await api.updateGroup(group, { name: trimmed, emoji })
      await reloadHosts()
      toast(
        result.hosts_updated
          ? `Group renamed - ${result.hosts_updated} host${result.hosts_updated === 1 ? '' : 's'} moved`
          : 'Group updated',
        'success',
      )
      onClose()
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : 'Could not save the group')
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent title="Edit group" description={`${hostCount} host${hostCount === 1 ? '' : 's'} in this group`}>
        <DialogBody className="space-y-4">
          <Field
            label="Group"
            htmlFor="groupTitle"
            hint={renaming
              ? `Every host in '${group}' moves to '${trimmed}'.`
              : undefined}
          >
            <Input
              id="groupTitle"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && dirty) save() }}
              autoFocus
            />
          </Field>

          <Field label="Icon" optional hint="Shown before the name in the sidebar and the host list.">
            <EmojiMartPicker id="groupEmoji" value={emoji} onChange={setEmoji} label="group icon" />
          </Field>

          {error && <p className="text-[13px] text-destructive">{error}</p>}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={!dirty || !trimmed || saving}>
            {saving ? 'Saving…' : 'Save group'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
