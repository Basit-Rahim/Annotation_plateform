export type Role = 'admin' | 'annotator'
export type Layer = 'layer_1' | 'layer_2'

export interface Me {
  id: string
  email: string
  role: Role
  can_layer_1: boolean
  can_layer_2: boolean
}

export interface UserRow extends Me {
  is_active: boolean
  created_at: string
}

export interface Token {
  word_index: number
  printed_word: string
}

export interface Passage {
  id: string
  code: string
  title: string
  urdu_text: string
  created_at: string
  tokens: Token[]
}

export interface ScanFile {
  filename: string
  size_bytes: number
  duration_seconds: number | null
}

export interface RecordingRow {
  id: string
  source_ref: string
  duration_seconds: string | null
  passage_code: string
  passage_attempt: number
  grade: number
  gender: string
  noise_level: string
  ingested_at: string
  withdrawn_at: string | null
  withdrawn_reason: string | null
  task_statuses: Partial<Record<Layer, string>>
}

export interface Stats {
  recordings_total: number
  tasks_available: number
  tasks_in_progress: number
  tasks_submitted: number
  annotators: number
  last_export_at: string | null
}

export interface Task {
  id: string
  layer: Layer
  status: string
  checked_out_at: string | null
  lease_expires_at: string | null
  recording_id: string
  passage_code: string
  duration_seconds: number | null
  audio_url: string
  tokens: Token[] | null
}

export interface DraftOut {
  payload: unknown
  updated_at: string
}

export interface DraftSaved {
  updated_at: string
  lease_expires_at: string | null
}

export interface Marks {
  first: number | null
  last: number | null
  boundary: number | null
}

export const MARK_KEYS = ['first', 'last', 'boundary'] as const
export type MarkKey = (typeof MARK_KEYS)[number]

export function marksComplete(m: Marks): boolean {
  return m.first !== null && m.last !== null && m.boundary !== null
}

export function marksPayload(m: Marks) {
  return {
    first_word_mark_seconds: m.first,
    last_word_mark_seconds: m.last,
    boundary_60s_mark_seconds: m.boundary,
  }
}

/** Annex E.1 closed list, in order. */
export const ERROR_TAGS: { code: string; label: string; countsAsError: boolean | null }[] = [
  { code: 'SUB', label: 'Substitution', countsAsError: true },
  { code: 'MIS', label: 'Mispronunciation', countsAsError: true },
  { code: 'OMI', label: 'Omission', countsAsError: true },
  { code: 'INS', label: 'Insertion', countsAsError: null },
  { code: 'PRO', label: 'Prompted', countsAsError: true },
  { code: 'SC', label: 'Self-correction', countsAsError: false },
  { code: 'REP', label: 'Repetition', countsAsError: false },
  { code: 'HES', label: 'Hesitation', countsAsError: false },
  { code: 'PAR', label: 'Partial word', countsAsError: true },
  { code: 'CS', label: 'Code-switch', countsAsError: true },
  { code: 'TRN', label: 'Transposition', countsAsError: false },
  { code: 'UNI', label: 'Unintelligible', countsAsError: true },
]
