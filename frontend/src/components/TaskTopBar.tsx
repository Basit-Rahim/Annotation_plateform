import { useEffect, useState } from 'react'
import type { Task } from '../api/types'
import { saveStateText, type SaveState } from './useTaskDraft'

function useMinutesLeft(expires: string | null): number | null {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  if (!expires) return null
  return Math.max(0, Math.floor((new Date(expires).getTime() - now) / 60_000))
}

interface Props {
  task: Task
  title: string
  canSubmit: boolean
  busy: boolean
  hint?: string
  saveState: SaveState
  onRelease: () => void
  onSubmit: () => void
}

export function TaskTopBar({ task, title, canSubmit, busy, hint, saveState, onRelease, onSubmit }: Props) {
  const minutesLeft = useMinutesLeft(task.lease_expires_at)
  return (
    <div className="topbar">
      <strong>{title}</strong>
      <div className="meta">
        <span>
          Task <b title={task.id}>{task.id.slice(0, 8)}</b>
        </span>
        <span>
          Passage <b>{task.passage_code}</b>
        </span>
        {minutesLeft !== null && <span className="muted">Lease: {minutesLeft} min left</span>}
      </div>
      <div className="spacer" />
      <span className={`save-state ${saveState.kind}`}>{saveStateText(saveState)}</span>
      {hint && <span className="muted small-text">{hint}</span>}
      <button className="danger" disabled={busy} onClick={onRelease}>
        Release
      </button>
      <button className="primary" disabled={!canSubmit || busy} onClick={onSubmit}>
        Submit
      </button>
    </div>
  )
}
