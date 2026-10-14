import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api/client'
import type { Passage } from '../api/types'
import { Alert } from '../components/Alert'

export function Passages() {
  const [passages, setPassages] = useState<Passage[]>([])
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    api.passages().then(setPassages).catch((err) => setError(errorMessage(err)))
  }, [])

  const preview = text.split(/\s+/).filter(Boolean)

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    try {
      const p = await api.createPassage({ code, title, urdu_text: text })
      setPassages((all) => [...all, p].sort((a, b) => a.code.localeCompare(b.code)))
      setSuccess(`Passage ${p.code} created with ${p.tokens.length} words.`)
      setOpen(p.id)
      setCode('')
      setTitle('')
      setText('')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <h1>Passages</h1>
      <Alert kind="error">{error}</Alert>
      <Alert kind="success">{success}</Alert>

      <form className="panel" onSubmit={onCreate}>
        <h2 style={{ marginTop: 0 }}>New passage</h2>
        <div className="form-grid">
          <label className="field">
            Code
            <input required placeholder="P01" value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
          <label className="field">
            Title
            <input required value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
        </div>
        <label className="field" style={{ marginTop: '0.75rem' }}>
          Urdu text (split into words on whitespace)
          <textarea
            className="urdu"
            dir="rtl"
            lang="ur"
            required
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <div className="row" style={{ marginTop: '0.75rem' }}>
          <button className="primary" type="submit">
            Create passage
          </button>
          <span className="muted small-text">{preview.length} words</span>
        </div>
      </form>

      <h2>Existing passages</h2>
      {passages.length === 0 && <p className="muted">No passages yet.</p>}
      <table className="data">
        <tbody>
          {passages.map((p) => (
            <tr key={p.id}>
              <td style={{ width: '6rem', verticalAlign: 'top' }}>
                <b>{p.code}</b>
              </td>
              <td>
                <div className="row">
                  <span>{p.title}</span>
                  <span className="muted small-text">{p.tokens.length} words</span>
                  <button className="small" onClick={() => setOpen(open === p.id ? null : p.id)}>
                    {open === p.id ? 'Hide words' : 'Show words'}
                  </button>
                </div>
                {open === p.id && (
                  <table className="grid" style={{ marginTop: '0.5rem' }}>
                    <tbody>
                      {p.tokens.map((t) => (
                        <tr key={t.word_index}>
                          <td className="idx">{t.word_index}</td>
                          <td className="word urdu">{t.printed_word}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
