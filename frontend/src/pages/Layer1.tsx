import { useLayoutEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, API_BASE, errorMessage } from '../api/client'
import { marksComplete, marksPayload, type MarkKey, type Marks } from '../api/types'
import { Alert } from '../components/Alert'
import { TaskTopBar } from '../components/TaskTopBar'
import { saveStateText, useTaskDraft } from '../components/useTaskDraft'
import { useWorkspaceTask } from '../components/useWorkspaceTask'
import { Waveform } from '../components/Waveform'

const TOKENS = ['[unintelligible]', '[non-target speech]', '[code-switch]']
const NO_MARKS: Marks = { first: null, last: null, boundary: null }

interface Draft {
  transcript: string
  marks: Marks
}

export function Layer1() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { task, loading, lost } = useWorkspaceTask(taskId, 'layer_1')
  const [transcript, setTranscript] = useState('')
  const [marks, setMarks] = useState<Marks>(NO_MARKS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const pendingCaret = useRef<number | null>(null)

  // Keyed on the id, not the task object: lease polling replaces the object
  // and must not re-restore a stale draft over what the annotator is typing.
  const draft = useTaskDraft<Draft>(
    task?.id,
    { transcript, marks },
    (saved) => {
      setTranscript(saved.transcript ?? '')
      setMarks({ ...NO_MARKS, ...saved.marks })
    },
    !lost,
  )

  function setMark(key: MarkKey, seconds: number) {
    setMarks((m) => ({ ...m, [key]: seconds }))
  }

  function insertToken(token: string) {
    const el = textareaRef.current
    if (!el) return
    const start = el.selectionStart ?? transcript.length
    const end = el.selectionEnd ?? start
    const before = transcript.slice(0, start)
    const after = transcript.slice(end)
    const insert = (before && !/\s$/.test(before) ? ' ' : '') + token + (after && !/^\s/.test(after) ? ' ' : '')
    pendingCaret.current = start + insert.length
    setTranscript(before + insert + after)
  }

  // Place the caret after an inserted token as soon as React commits the new
  // value, before any further keystroke can land in the wrong position.
  useLayoutEffect(() => {
    const el = textareaRef.current
    if (pendingCaret.current === null || !el) return
    el.focus()
    el.setSelectionRange(pendingCaret.current, pendingCaret.current)
    pendingCaret.current = null
  }, [transcript])

  async function release() {
    if (!task || !window.confirm('Release this task? Your draft will be discarded.')) return
    setBusy(true)
    try {
      await api.release(task.id)
      draft.discard()
      navigate('/queue', { state: { flash: 'Task released back to the pool.' } })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  async function submit() {
    if (!task) return
    setBusy(true)
    setError(null)
    try {
      await api.submit(task.id, 'layer_1', { transcript_urdu: transcript, ...marksPayload(marks) })
      draft.discard()
      navigate('/queue', { state: { flash: 'Layer 1 transcript submitted. Thank you!' } })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  if (loading || (task && !draft.restored)) return <p className="muted">Loading task…</p>
  if (!task) {
    return (
      <>
        <Alert kind="error">{lost}</Alert>
        <Link to="/queue">Back to my queue</Link>
      </>
    )
  }

  const canSubmit = !lost && marksComplete(marks) && transcript.trim().length > 0
  const hint = !marksComplete(marks) ? 'Set all three marks' : !transcript.trim() ? 'Transcript is empty' : undefined

  return (
    <>
      <div className="workspace-head">
        <TaskTopBar
          task={task}
          title="Layer 1 · Verbatim transcript"
          canSubmit={canSubmit}
          busy={busy}
          hint={hint}
          onRelease={release}
          onSubmit={submit}
          saveState={draft.state}
        />
        <Alert kind="error">{lost && <>{lost} <Link to="/queue">Back to my queue</Link></>}</Alert>
        <Alert kind="error">{error}</Alert>
        <div className="panel">
          <Waveform url={API_BASE + task.audio_url} marks={marks} onMarkChange={setMark} />
        </div>
      </div>
      <div className="panel">
        <div className="row" style={{ marginBottom: '0.5rem' }}>
          <strong>Transcript</strong>
          <span className="muted small-text">Type exactly what the child said, including mispronunciations.</span>
          <div className="spacer" />
          {TOKENS.map((t) => (
            <button key={t} className="small" onClick={() => insertToken(t)}>
              {t}
            </button>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          className="transcript"
          dir="rtl"
          lang="ur"
          aria-label="Transcript"
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          spellCheck={false}
        />
        <div className="muted small-text">{saveStateText(draft.state)}</div>
      </div>
    </>
  )
}
