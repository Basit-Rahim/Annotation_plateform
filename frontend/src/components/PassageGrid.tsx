import { Fragment } from 'react'
import { ERROR_TAGS, type Token } from '../api/types'
import { InsertionSlot } from './InsertionSlot'

export interface Judgement {
  is_error: boolean | null
  error_tag: string | null
}

export function isJudged(j: Judgement | undefined): boolean {
  if (!j || j.is_error === null) return false
  return j.is_error ? j.error_tag !== null : true
}

const TAG_BY_CODE = Object.fromEntries(ERROR_TAGS.map((t) => [t.code, t]))

/** Picking a tag implies the chip; picking a chip clears a tag that contradicts it. */
function withTag(j: Judgement, tag: string | null): Judgement {
  const counts = tag ? TAG_BY_CODE[tag]?.countsAsError : null
  return { error_tag: tag, is_error: counts === true ? true : counts === false ? false : j.is_error }
}

function withChip(j: Judgement, isError: boolean): Judgement {
  const counts = j.error_tag ? TAG_BY_CODE[j.error_tag]?.countsAsError : null
  const keepTag = counts === null || counts === undefined ? false : counts === isError
  return { is_error: isError, error_tag: keepTag ? j.error_tag : null }
}

interface Props {
  tokens: Token[]
  judgements: Record<number, Judgement>
  insertions: Record<number, string[]>
  onJudgement: (wordIndex: number, j: Judgement) => void
  onInsertions: (afterWordIndex: number, words: string[]) => void
}

const EMPTY: Judgement = { is_error: null, error_tag: null }
const COLS = 4

export function PassageGrid({ tokens, judgements, insertions, onJudgement, onInsertions }: Props) {
  return (
    <table className="grid">
      <thead>
        <tr>
          <th>#</th>
          <th style={{ textAlign: 'right' }}>Printed word</th>
          <th>Error tag</th>
          <th>Judgement</th>
        </tr>
      </thead>
      <tbody>
        <InsertionSlot afterWordIndex={0} words={insertions[0] ?? []} onChange={(w) => onInsertions(0, w)} colSpan={COLS} />
        {tokens.map((t) => {
          const j = judgements[t.word_index] ?? EMPTY
          const rowClass = j.is_error === null ? '' : j.is_error ? 'judged-err' : 'judged-ok'
          return (
            <Fragment key={t.word_index}>
              <tr className={`word-row ${rowClass}`} data-word={t.word_index}>
                <td className="idx">{t.word_index}</td>
                <td className="word urdu" dir="rtl">
                  {t.printed_word}
                </td>
                <td>
                  <select
                    aria-label={`Error tag for word ${t.word_index}`}
                    value={j.error_tag ?? ''}
                    onChange={(e) => onJudgement(t.word_index, withTag(j, e.target.value || null))}
                  >
                    <option value="">— none —</option>
                    {ERROR_TAGS.map((tag) => (
                      <option key={tag.code} value={tag.code} disabled={tag.code === 'INS'}>
                        {tag.code} — {tag.label}
                        {tag.code === 'INS' ? ' (use insertion slots)' : ''}
                      </option>
                    ))}
                  </select>
                  {j.is_error && !j.error_tag && <span className="muted small-text"> pick a tag</span>}
                </td>
                <td>
                  <button
                    className={`chip ok small ${j.is_error === false ? 'on' : ''}`}
                    onClick={() => onJudgement(t.word_index, withChip(j, false))}
                  >
                    Correct
                  </button>
                  <button
                    className={`chip err small ${j.is_error === true ? 'on' : ''}`}
                    onClick={() => onJudgement(t.word_index, withChip(j, true))}
                  >
                    Error
                  </button>
                </td>
              </tr>
              <InsertionSlot
                afterWordIndex={t.word_index}
                words={insertions[t.word_index] ?? []}
                onChange={(w) => onInsertions(t.word_index, w)}
                colSpan={COLS}
              />
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
