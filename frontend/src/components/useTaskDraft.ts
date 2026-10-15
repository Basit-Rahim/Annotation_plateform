import { useCallback, useEffect, useRef, useState } from 'react'
import { api, API_BASE, ApiError } from '../api/client'
import { useAuth } from './AuthProvider'

const SAVE_DELAY_MS = 1500
const RETRY_MS = 10_000

export type SaveState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved'; at: Date }
  /** Server unreachable: the work is kept in this browser and retried. */
  | { kind: 'offline' }
  /** Server refused the save (e.g. lease gone, logged out); kept in this browser. */
  | { kind: 'rejected'; message: string }

interface LocalEntry {
  payload: unknown
  /** True while this copy has changes the server has not confirmed. */
  dirty: boolean
}

// Scoped by user too, so a shared computer never restores someone else's work.
const localKey = (key: string) => `annot:draft:${key}`

function readLocal(taskId: string): LocalEntry | null {
  try {
    const raw = localStorage.getItem(localKey(taskId))
    return raw ? (JSON.parse(raw) as LocalEntry) : null
  } catch {
    return null
  }
}

function writeLocal(taskId: string, entry: LocalEntry) {
  try {
    localStorage.setItem(localKey(taskId), JSON.stringify(entry))
  } catch {
    /* storage full or blocked: the server copy still applies */
  }
}

/**
 * Keep a workspace's unfinished work safe. Every change is written to this
 * browser immediately and to the server shortly after (which also renews the
 * lease). On load, local changes the server never confirmed win over the
 * server copy, so a crash, a closed tab or a dropped connection loses nothing.
 */
export function useTaskDraft<T>(task: string | undefined, value: T, restore: (saved: T) => void, active: boolean) {
  const { user } = useAuth()
  const taskId = task && user ? task : undefined
  const storeKey = taskId && user ? `${user.id}:${taskId}` : undefined
  const [restored, setRestored] = useState(false)
  const [state, setState] = useState<SaveState>({ kind: 'idle' })
  const json = JSON.stringify(value)

  const jsonRef = useRef(json)
  jsonRef.current = json
  const restoreRef = useRef(restore)
  restoreRef.current = restore
  const taskRef = useRef(taskId)
  taskRef.current = taskId
  const keyRef = useRef(storeKey)
  keyRef.current = storeKey
  const done = useRef(false) // submitted or released
  const live = useRef(false) // restored, still checked out, not done
  live.current = restored && active && !done.current
  const confirmed = useRef<string | null>(null) // last JSON the server accepted
  const pushing = useRef(false)

  const push = useCallback(async () => {
    const id = taskRef.current
    const body = jsonRef.current
    if (!id || !live.current || pushing.current || body === confirmed.current) return
    pushing.current = true
    setState({ kind: 'saving' })
    try {
      await api.saveDraft(id, JSON.parse(body))
      confirmed.current = body
      if (jsonRef.current === body && keyRef.current) writeLocal(keyRef.current, { payload: JSON.parse(body), dirty: false })
      setState({ kind: 'saved', at: new Date() })
    } catch (err) {
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
        setState({ kind: 'rejected', message: err.message })
      } else {
        setState({ kind: 'offline' })
      }
    } finally {
      pushing.current = false
    }
  }, [])

  // Restore once per task.
  useEffect(() => {
    if (!taskId || !storeKey) return
    let cancelled = false
    setRestored(false)
    confirmed.current = null
    void (async () => {
      const local = readLocal(storeKey)
      let server: unknown = null
      try {
        server = (await api.getDraft(taskId))?.payload ?? null
      } catch {
        /* offline: fall back to the local copy */
      }
      if (cancelled) return
      const pick = local?.dirty ? local.payload : (server ?? local?.payload ?? null)
      if (pick !== null) restoreRef.current(pick as T)
      if (!local?.dirty && server !== null) confirmed.current = JSON.stringify(server)
      setRestored(true)
    })()
    return () => {
      cancelled = true
    }
  }, [taskId, storeKey])

  // Every change: local copy now, server copy after a short pause in typing.
  useEffect(() => {
    if (!storeKey || !restored || !active || done.current || json === confirmed.current) return
    writeLocal(storeKey, { payload: JSON.parse(json), dirty: true })
    const timer = window.setTimeout(() => void push(), SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [json, storeKey, restored, active, push])

  // Retry anything unsent (offline, or edits made while a save was in flight).
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (jsonRef.current !== confirmed.current) void push()
    }, RETRY_MS)
    return () => window.clearInterval(timer)
  }, [push])

  // Closing the tab or leaving the page: best-effort final save.
  useEffect(() => {
    function flush() {
      const id = taskRef.current
      if (!id || !live.current || jsonRef.current === confirmed.current) return
      try {
        void fetch(`${API_BASE}/api/tasks/${id}/draft`, {
          method: 'PUT',
          keepalive: true,
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: `{"payload":${jsonRef.current}}`,
        }).catch(() => undefined)
      } catch {
        /* the local copy is still there */
      }
    }
    window.addEventListener('pagehide', flush)
    return () => {
      window.removeEventListener('pagehide', flush)
      flush() // in-app navigation away from the workspace
    }
  }, [])

  /** Call after a successful submit or release: the draft is no longer needed. */
  const discard = useCallback(() => {
    done.current = true
    live.current = false
    if (keyRef.current) {
      try {
        localStorage.removeItem(localKey(keyRef.current))
      } catch {
        /* ignore */
      }
    }
  }, [])

  return { restored, state, discard }
}

export function saveStateText(state: SaveState): string {
  switch (state.kind) {
    case 'idle':
      return 'Changes save automatically.'
    case 'saving':
      return 'Saving…'
    case 'saved':
      return `All changes saved · ${state.at.toLocaleTimeString()}`
    case 'offline':
      return 'Server unreachable · work kept in this browser, retrying'
    case 'rejected':
      return `Not saved to server (${state.message}) · work kept in this browser`
  }
}
