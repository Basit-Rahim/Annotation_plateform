import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { RecordingRow, Stats } from '../api/types'
import { Alert } from '../components/Alert'

function StatusBadge({ status }: { status?: string }) {
  return status ? <span className={`badge ${status}`}>{status.replace('_', ' ')}</span> : <span className="muted">—</span>
}

export function AdminDashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [recordings, setRecordings] = useState<RecordingRow[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.stats(), api.recordings()])
      setStats(s)
      setRecordings(r)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function withdraw(rec: RecordingRow) {
    const reason = window.prompt(
      `Withdraw recording ${rec.source_ref}? This deletes the audio file and cancels its tasks.\n\nReason:`,
    )
    if (!reason?.trim()) return
    try {
      await api.withdraw(rec.id, reason.trim())
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const cards: [string, number | undefined][] = [
    ['Recordings', stats?.recordings_total],
    ['Available tasks', stats?.tasks_available],
    ['In progress', stats?.tasks_in_progress],
    ['Submitted', stats?.tasks_submitted],
    ['Annotators', stats?.annotators],
  ]

  return (
    <>
      <h1>Dashboard</h1>
      <Alert kind="error">{error}</Alert>
      <div className="stats">
        {cards.map(([label, n]) => (
          <div className="stat" key={label}>
            <div className="n">{n ?? '…'}</div>
            <div className="l">{label}</div>
          </div>
        ))}
      </div>

      <h2>Recordings</h2>
      {recordings.length === 0 ? (
        <p className="muted">No recordings yet. Drop audio into the incoming folder and use Ingest audio.</p>
      ) : (
        <table className="data">
          <thead>
            <tr>
              <th>File</th>
              <th>Passage</th>
              <th>Grade</th>
              <th>Duration</th>
              <th>Ingested</th>
              <th>Layer 1</th>
              <th>Layer 2</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {recordings.map((r) => (
              <tr key={r.id}>
                <td title={r.id}>{r.source_ref}</td>
                <td>
                  {r.passage_code} <span className="muted small-text">(attempt {r.passage_attempt})</span>
                </td>
                <td>{r.grade}</td>
                <td>{r.duration_seconds ? `${Number(r.duration_seconds).toFixed(1)}s` : '—'}</td>
                <td>{new Date(r.ingested_at).toLocaleString()}</td>
                <td><StatusBadge status={r.task_statuses.layer_1} /></td>
                <td><StatusBadge status={r.task_statuses.layer_2} /></td>
                <td>
                  {r.withdrawn_at ? (
                    <span className="muted small-text" title={r.withdrawn_reason ?? ''}>withdrawn</span>
                  ) : (
                    <button className="small danger" onClick={() => withdraw(r)}>Withdraw</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
