import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api/client'
import type { Passage, ScanFile } from '../api/types'
import { Alert } from '../components/Alert'
import { Modal } from '../components/Modal'

interface Meta {
  passage_id: string
  passage_attempt: number
  grade: number
  gender: string
  first_language: string
  school_type: string
  noise_level: 'quiet' | 'moderate' | 'noisy'
  interruption: boolean
  assessor_notes: string
}

const DEFAULT_META: Meta = {
  passage_id: '',
  passage_attempt: 1,
  grade: 2,
  gender: '',
  first_language: 'Urdu',
  school_type: '',
  noise_level: 'quiet',
  interruption: false,
  assessor_notes: '',
}

function IngestForm({ file, passages, onDone, onCancel }: {
  file: ScanFile
  passages: Passage[]
  onDone: (msg: string) => void
  onCancel: () => void
}) {
  const [meta, setMeta] = useState<Meta>({ ...DEFAULT_META, passage_id: passages[0]?.id ?? '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof Meta>(k: K, v: Meta[K]) => setMeta((m) => ({ ...m, [k]: v }))

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.ingest(file.filename, { ...meta, assessor_notes: meta.assessor_notes.trim() || null })
      onDone(`${file.filename} ingested; Layer 1 and Layer 2 tasks created.`)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <Modal title={`Ingest ${file.filename}`} onClose={onCancel}>
      <Alert kind="error">{error}</Alert>
      {passages.length === 0 && <Alert kind="info">Create a passage first.</Alert>}
      <form onSubmit={onSubmit}>
        <div className="form-grid">
          <label className="field">
            Passage
            <select required value={meta.passage_id} onChange={(e) => set('passage_id', e.target.value)}>
              {passages.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} — {p.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Passage attempt
            <select value={meta.passage_attempt} onChange={(e) => set('passage_attempt', Number(e.target.value))}>
              <option value={1}>1</option>
              <option value={2}>2</option>
            </select>
          </label>
          <label className="field">
            Grade
            <input type="number" min={1} max={12} required value={meta.grade} onChange={(e) => set('grade', Number(e.target.value))} />
          </label>
          <label className="field">
            Gender
            <select required value={meta.gender} onChange={(e) => set('gender', e.target.value)}>
              <option value="" disabled>Select…</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </label>
          <label className="field">
            First language
            <input required list="languages" value={meta.first_language} onChange={(e) => set('first_language', e.target.value)} />
            <datalist id="languages">
              {['Urdu', 'Punjabi', 'Pashto', 'Sindhi', 'Saraiki', 'Balochi', 'Other'].map((l) => <option key={l} value={l} />)}
            </datalist>
          </label>
          <label className="field">
            School type
            <input required list="school-types" value={meta.school_type} onChange={(e) => set('school_type', e.target.value)} />
            <datalist id="school-types">
              {['public', 'private', 'trust / NGO'].map((s) => <option key={s} value={s} />)}
            </datalist>
          </label>
          <label className="field">
            Noise level
            <select value={meta.noise_level} onChange={(e) => set('noise_level', e.target.value as Meta['noise_level'])}>
              <option value="quiet">Quiet</option>
              <option value="moderate">Moderate</option>
              <option value="noisy">Noisy</option>
            </select>
          </label>
          <label className="check" style={{ marginTop: '1.4rem' }}>
            <input type="checkbox" checked={meta.interruption} onChange={(e) => set('interruption', e.target.checked)} />
            Interruption during recording
          </label>
        </div>
        <label className="field" style={{ marginTop: '0.75rem' }}>
          Assessor notes (optional)
          <textarea rows={2} value={meta.assessor_notes} onChange={(e) => set('assessor_notes', e.target.value)} />
        </label>
        <div className="row" style={{ marginTop: '1rem' }}>
          <button className="primary" type="submit" disabled={busy || passages.length === 0}>
            Ingest
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function Ingest() {
  const [files, setFiles] = useState<ScanFile[] | null>(null)
  const [passages, setPassages] = useState<Passage[]>([])
  const [selected, setSelected] = useState<ScanFile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    api.passages().then(setPassages).catch((err) => setError(errorMessage(err)))
  }, [])

  async function scan() {
    setScanning(true)
    setError(null)
    try {
      setFiles(await api.scan())
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setScanning(false)
    }
  }

  return (
    <>
      <h1>Ingest audio</h1>
      <p className="muted">
        Copy audio files into the <code>data/incoming/</code> folder, then scan. Ingesting moves a file into storage and
        creates one Layer 1 and one Layer 2 task.
      </p>
      <Alert kind="error">{error}</Alert>
      <Alert kind="success">{success}</Alert>
      <button className="primary" onClick={scan} disabled={scanning}>
        {scanning ? 'Scanning…' : 'Scan folder'}
      </button>

      {files && (
        <div style={{ marginTop: '1rem' }}>
          {files.length === 0 ? (
            <p className="muted">No new audio files in the drop folder.</p>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Size</th>
                  <th>Duration</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.filename}>
                    <td>{f.filename}</td>
                    <td>{(f.size_bytes / 1024).toFixed(0)} KB</td>
                    <td>{f.duration_seconds !== null ? `${f.duration_seconds.toFixed(1)}s` : 'unknown'}</td>
                    <td>
                      <button className="small" onClick={() => setSelected(f)}>
                        Ingest
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {selected && (
        <IngestForm
          file={selected}
          passages={passages}
          onCancel={() => setSelected(null)}
          onDone={(msg) => {
            setSuccess(msg)
            setFiles((all) => all?.filter((f) => f.filename !== selected.filename) ?? null)
            setSelected(null)
          }}
        />
      )}
    </>
  )
}
