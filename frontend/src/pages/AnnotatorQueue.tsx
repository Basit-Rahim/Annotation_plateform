import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError, errorMessage } from '../api/client'
import type { Layer, Task } from '../api/types'
import { Alert } from '../components/Alert'
import { useAuth } from '../components/AuthProvider'

const LAYER_LABEL: Record<Layer, string> = { layer_1: 'Layer 1', layer_2: 'Layer 2' }

export function workspacePath(task: Task): string {
  return `/annotate/${task.layer === 'layer_1' ? 'layer-1' : 'layer-2'}/${task.id}`
}

export function AnnotatorQueue() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash
  const [current, setCurrent] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setCurrent(await api.currentTask())
    } catch (err) {
      setMessage(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function takeNext(layer: Layer) {
    setBusy(true)
    setMessage(null)
    try {
      const task = await api.takeNext(layer)
      navigate(workspacePath(task))
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMessage(`No ${LAYER_LABEL[layer]} tasks are available right now.`)
      else if (err instanceof ApiError && err.status === 409) {
        setMessage('You already have a task checked out.')
        await refresh()
      } else setMessage(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="muted">Loading…</p>

  return (
    <>
      <h1>My queue</h1>
      <Alert kind="success">{flash}</Alert>
      <Alert kind="info">{message}</Alert>
      {current ? (
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Your current task</h2>
          <p>
            {LAYER_LABEL[current.layer]} · passage <b>{current.passage_code}</b> · task{' '}
            <code title={current.id}>{current.id.slice(0, 8)}</code>
          </p>
          <p className="muted small-text">
            Checked out {current.checked_out_at && new Date(current.checked_out_at).toLocaleString()} · lease expires{' '}
            {current.lease_expires_at && new Date(current.lease_expires_at).toLocaleTimeString()}. Finish it (submit or
            release) before taking another.
          </p>
          <button className="primary big" onClick={() => navigate(workspacePath(current))}>
            Open
          </button>
        </div>
      ) : (
        <div className="panel">
          <p>You have no task checked out. Take the next recording from the pool:</p>
          <div className="row">
            <button className="primary big" disabled={busy || !user?.can_layer_1} onClick={() => takeNext('layer_1')}>
              Take next Layer 1
            </button>
            <button className="primary big" disabled={busy || !user?.can_layer_2} onClick={() => takeNext('layer_2')}>
              Take next Layer 2
            </button>
          </div>
          <p className="muted small-text">
            Layer 1: verbatim transcript. Layer 2: word-by-word scoring. Greyed-out buttons are layers you are not
            eligible for. Each task is reserved for you for 120 minutes.
          </p>
        </div>
      )}
    </>
  )
}
