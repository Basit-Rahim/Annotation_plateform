import type { DraftOut, DraftSaved, Layer, Me, Passage, RecordingRow, ScanFile, Stats, Task, UserRow } from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

function detailMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  return fallback
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method,
    credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailMessage(data, res.statusText))
  return data as T
}

const get = <T>(path: string) => request<T>('GET', path)
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
const patch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
const put = <T>(path: string, body: unknown) => request<T>('PUT', path, body)

export const api = {
  login: (email: string, password: string) => post<Me>('/api/auth/login', { email, password }),
  logout: () => post<void>('/api/auth/logout'),
  me: () => get<Me>('/api/auth/me'),

  stats: () => get<Stats>('/api/admin/stats'),
  recordings: () => get<RecordingRow[]>('/api/admin/recordings'),
  withdraw: (id: string, reason: string) => post(`/api/admin/recordings/${id}/withdraw`, { reason }),

  users: () => get<UserRow[]>('/api/admin/users'),
  createUser: (body: { email: string; password: string; can_layer_1: boolean; can_layer_2: boolean }) =>
    post<UserRow>('/api/admin/users', body),
  updateUser: (id: string, body: Partial<Pick<UserRow, 'is_active' | 'can_layer_1' | 'can_layer_2'>>) =>
    patch<UserRow>(`/api/admin/users/${id}`, body),
  resetPassword: (id: string, password: string) => post<void>(`/api/admin/users/${id}/reset-password`, { password }),

  passages: () => get<Passage[]>('/api/admin/passages'),
  createPassage: (body: { code: string; title: string; urdu_text: string }) =>
    post<Passage>('/api/admin/passages', body),

  scan: () => get<ScanFile[]>('/api/admin/ingest/scan'),
  ingest: (filename: string, body: Record<string, unknown>) =>
    post(`/api/admin/ingest/${encodeURIComponent(filename)}`, body),

  takeNext: (layer: Layer) => get<Task>(`/api/pool/next?layer=${layer}`),
  currentTask: () => get<Task | null>('/api/tasks/current'),
  release: (taskId: string) => post<void>(`/api/tasks/${taskId}/release`),
  submit: (taskId: string, layer: Layer, body: unknown) => post(`/api/tasks/${taskId}/submit/${layer}`, body),
  getDraft: (taskId: string) => get<DraftOut | null>(`/api/tasks/${taskId}/draft`),
  saveDraft: (taskId: string, payload: unknown) => put<DraftSaved>(`/api/tasks/${taskId}/draft`, { payload }),
}

/** Download the export as a file, keeping the server-provided filename. */
export async function downloadExport(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/export`, { credentials: 'include' })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new ApiError(res.status, detailMessage(data, res.statusText))
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'annotations.json'
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}
