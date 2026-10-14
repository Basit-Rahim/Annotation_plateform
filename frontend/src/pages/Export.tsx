import { useEffect, useState } from 'react'
import { api, downloadExport, errorMessage } from '../api/client'
import { Alert } from '../components/Alert'

export function Export() {
  const [lastExport, setLastExport] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadStats() {
    const s = await api.stats()
    setLastExport(s.last_export_at)
    setSubmitted(s.tasks_submitted)
  }

  useEffect(() => {
    loadStats().catch((err) => setError(errorMessage(err)))
  }, [])

  async function download() {
    setBusy(true)
    setError(null)
    try {
      await downloadExport()
      await loadStats()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Export</h1>
      <Alert kind="error">{error}</Alert>
      <div className="panel">
        <p>
          Downloads every submitted annotation (Layer 1 and Layer 2) as JSON. Urdu text is included both raw and
          normalised (Annex E.4); the file records the normalisation and schema versions. Withdrawn recordings are
          excluded.
        </p>
        <p className="muted">
          Submitted tasks: {submitted ?? '…'} · Last export:{' '}
          {lastExport ? new Date(lastExport).toLocaleString() : 'never'}
        </p>
        <button className="primary big" onClick={download} disabled={busy}>
          {busy ? 'Preparing…' : 'Download JSON'}
        </button>
      </div>
    </>
  )
}
