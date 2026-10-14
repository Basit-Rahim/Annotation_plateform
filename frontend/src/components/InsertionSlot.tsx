import { useState } from 'react'

interface Props {
  afterWordIndex: number
  words: string[]
  onChange: (words: string[]) => void
  colSpan: number
}

/** A row between printed words where a teacher records words the child inserted (INS). */
export function InsertionSlot({ afterWordIndex, words, onChange, colSpan }: Props) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')

  function add() {
    const text = draft.trim()
    if (!text) return
    onChange([...words, text])
    setDraft('')
    setOpen(false)
  }

  const label = afterWordIndex === 0 ? 'before word 1' : `after word ${afterWordIndex}`

  return (
    <tr className={`slot ${words.length ? 'has-items' : ''} ${open ? 'open' : ''}`} data-slot={afterWordIndex}>
      <td colSpan={colSpan}>
        <div className="slot-body">
          {words.map((w, i) => (
            <span key={i} className="ins-chip">
              <span className="badge">INS</span>
              <span className="urdu">{w}</span>
              <button
                className="slot-toggle"
                aria-label={`Remove inserted word ${w}`}
                onClick={() => onChange(words.filter((_, j) => j !== i))}
              >
                ✕
              </button>
            </span>
          ))}
          {open ? (
            <>
              <input
                className="urdu"
                dir="rtl"
                autoFocus
                value={draft}
                placeholder="لفظ"
                aria-label={`Inserted word ${label}`}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') add()
                  if (e.key === 'Escape') setOpen(false)
                }}
              />
              <button className="small primary" disabled={!draft.trim()} onClick={add}>
                Add
              </button>
              <button className="small" onClick={() => setOpen(false)}>
                Cancel
              </button>
            </>
          ) : (
            <button className="slot-toggle" title={`Insert word ${label}`} onClick={() => setOpen(true)}>
              + Insert word here
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}
