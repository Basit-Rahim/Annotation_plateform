import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, API_BASE, errorMessage } from '../api/client'
import { marksComplete, marksPayload, type MarkKey, type Marks } from '../api/types'
import { Alert } from '../components/Alert'
import { isJudged, PassageGrid, type Judgement } from '../components/PassageGrid'
import { TaskTopBar } from '../components/TaskTopBar'
import { useWorkspaceTask } from '../components/useWorkspaceTask'
import { Waveform } from '../components/Waveform'

export function Layer2() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { task, loading, lost } = useWorkspaceTask(taskId, 'layer_2')
  const [marks, setMarks] = useState<Marks>({ first: null, last: null, boundary: null })
  const [judgements, setJudgements] = useState<Record<number, Judgement>>({})
  const [insertions, setInsertions] = useState<Record<number, string[]>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function setMark(key: MarkKey, seconds: number) {
    setMarks((m) => ({ ...m, [key]: seconds }))
  }

  async function release() {
    if (!task || !window.confirm('Release this task? Your judgements will be discarded.')) return
    setBusy(true)
    try {
      await api.release(task.id)
      navigate('/queue', { state: { flash: 'Task released back to the pool.' } })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  async function submit() {
    if (!task?.tokens) return
    setBusy(true)
    setError(null)
    const body = {
      ...marksPayload(marks),
      words: task.tokens.map((t) => ({
        word_index: t.word_index,
        is_error: judgements[t.word_index].is_error,
        error_tag: judgements[t.word_index].error_tag,
      })),
      insertions: Object.entries(insertions).flatMap(([slot, words]) =>
        words.map((w, i) => ({ after_word_index: Number(slot), inserted_text: w, position_within_slot: i + 1 })),
      ),
    }
    try {
      await api.submit(task.id, 'layer_2', body)
      navigate('/queue', { state: { flash: 'Layer 2 scoring submitted. Thank you!' } })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  if (loading) return <p className="muted">Loading task…</p>
  if (!task?.tokens) {
    return (
      <>
        <Alert kind="error">{lost ?? 'This task has no passage words.'}</Alert>
        <Link to="/queue">Back to my queue</Link>
      </>
    )
  }

  const judged = task.tokens.filter((t) => isJudged(judgements[t.word_index])).length
  const total = task.tokens.length
  const canSubmit = !lost && marksComplete(marks) && judged === total
  const hint = !marksComplete(marks)
    ? `Set all three marks · ${judged}/${total} words judged`
    : judged < total
      ? `${judged}/${total} words judged`
      : undefined

  return (
    <>
      <div className="workspace-head">
        <TaskTopBar
          task={task}
          title="Layer 2 · Word-by-word scoring"
          canSubmit={canSubmit}
          busy={busy}
          hint={hint}
          onRelease={release}
          onSubmit={submit}
        />
        <Alert kind="error">{lost && <>{lost} <Link to="/queue">Back to my queue</Link></>}</Alert>
        <Alert kind="error">{error}</Alert>
        <div className="panel">
          <Waveform url={API_BASE + task.audio_url} marks={marks} onMarkChange={setMark} />
        </div>
      </div>
      <div className="panel">
        <PassageGrid
          tokens={task.tokens}
          judgements={judgements}
          insertions={insertions}
          onJudgement={(i, j) => setJudgements((all) => ({ ...all, [i]: j }))}
          onInsertions={(slot, words) => setInsertions((all) => ({ ...all, [slot]: words }))}
        />
      </div>
    </>
  )
}
