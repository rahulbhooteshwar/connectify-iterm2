/** Import (drag-drop JSON with preview) and export (hosts / template).
 * Secrets are never part of either - hosts carry a credential *name*. */

import * as React from 'react'
import { Download, FileJson, UploadCloud } from 'lucide-react'
import { useStore } from '../store'
import * as api from '../lib/api'
import { Badge, Button, cn, Dialog, DialogBody, DialogContent, DialogFooter, Spinner } from './ui'

interface ImportedHost {
  name?: string
  hostname?: string
  username?: string
  port?: number
  credential?: string
  tags?: string[]
  [key: string]: unknown
}

export function ImportDialog({ onClose }: { onClose: () => void }) {
  const { toast, reloadHosts } = useStore()
  const [hosts, setHosts] = React.useState<ImportedHost[] | null>(null)
  const [fileName, setFileName] = React.useState('')
  const [dragOver, setDragOver] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const fileInput = React.useRef<HTMLInputElement>(null)

  const readFile = async (file: File) => {
    setError('')
    try {
      const parsed = JSON.parse(await file.text())
      const list = Array.isArray(parsed) ? parsed : parsed?.hosts
      if (!Array.isArray(list) || list.length === 0) {
        setError('No hosts found in that file - expected {"hosts": [...]}')
        return
      }
      setHosts(list)
      setFileName(file.name)
    } catch {
      setError('That file is not valid JSON')
    }
  }

  const runImport = async () => {
    if (!hosts) return
    setBusy(true)
    setError('')
    try {
      const result = await api.importHosts(hosts)
      toast(result.message, result.errors?.length ? 'error' : 'success')
      for (const warning of result.warnings ?? []) toast(warning, 'info')
      await reloadHosts()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title="Import hosts" wide
        description="Secrets are never imported - hosts reference a vault credential by name.">
        <DialogBody className="space-y-3">
          {!hosts ? (
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const file = e.dataTransfer.files?.[0]
                if (file) readFile(file)
              }}
              className={cn(
                'flex w-full cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-10',
                'text-muted-foreground transition-colors',
                dragOver ? 'border-ring bg-accent text-accent-foreground' : 'border-border hover:border-ring hover:text-foreground',
              )}
            >
              <UploadCloud size={30} />
              <span className="text-sm font-medium">Drag &amp; drop a JSON file</span>
              <span className="text-xs">or click to browse</span>
            </button>
          ) : (
            <>
              <div className="flex items-center gap-2 text-sm">
                <FileJson size={15} className="text-muted-foreground" />
                <span className="font-medium">{fileName}</span>
                <Badge>{hosts.length} host{hosts.length === 1 ? '' : 's'}</Badge>
                <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setHosts(null)}>
                  Choose another file
                </Button>
              </div>
              <ul className="max-h-64 divide-y divide-border overflow-y-auto rounded-lg border border-border">
                {hosts.map((h, index) => (
                  <li key={index} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                    <div className="min-w-0">
                      <span className="font-medium">{h.name ?? '(unnamed)'}</span>
                      <span className="ml-2 font-mono text-xs text-muted-foreground">
                        {h.username ? `${h.username}@` : ''}{h.hostname}{h.port && h.port !== 22 ? `:${h.port}` : ''}
                      </span>
                    </div>
                    {h.credential
                      ? <Badge>{h.credential}</Badge>
                      : <Badge className="border-warning/40 text-warning">no credential</Badge>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {error && <p className="text-[13px] text-destructive">{error}</p>}
          <input
            ref={fileInput} type="file" accept=".json,application/json" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) readFile(f) }}
          />
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={runImport} disabled={!hosts || busy}>
            {busy && <Spinner />} Import {hosts ? hosts.length : ''} host{hosts?.length === 1 ? '' : 's'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function ExportDialog({ onClose }: { onClose: () => void }) {
  const { hosts } = useStore()
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent title="Export hosts"
        description="Exports never contain secrets - only the credential names hosts refer to.">
        <DialogBody className="grid grid-cols-2 gap-3">
          <a
            href="/api/export/hosts" download="ssh_hosts_export.json"
            className="flex flex-col items-center gap-2 rounded-xl border border-border px-4 py-6 text-center transition-colors hover:border-ring hover:bg-muted"
          >
            <Download size={22} className="text-primary" />
            <span className="text-sm font-semibold">Current hosts</span>
            <span className="text-xs text-muted-foreground">{hosts.length} configured host{hosts.length === 1 ? '' : 's'}</span>
          </a>
          <a
            href="/api/export/template" download="ssh_hosts_template.json"
            className="flex flex-col items-center gap-2 rounded-xl border border-border px-4 py-6 text-center transition-colors hover:border-ring hover:bg-muted"
          >
            <FileJson size={22} className="text-primary" />
            <span className="text-sm font-semibold">Sample template</span>
            <span className="text-xs text-muted-foreground">An example file to start from</span>
          </a>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
