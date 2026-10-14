import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api/client'
import type { UserRow } from '../api/types'
import { Alert } from '../components/Alert'

export function Users() {
  const [users, setUsers] = useState<UserRow[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [l1, setL1] = useState(true)
  const [l2, setL2] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    api.users().then(setUsers).catch((err) => setError(errorMessage(err)))
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    try {
      const u = await api.createUser({ email, password, can_layer_1: l1, can_layer_2: l2 })
      setUsers((all) => [...all, u])
      setSuccess(`Annotator ${u.email} created.`)
      setEmail('')
      setPassword('')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function update(u: UserRow, change: Partial<Pick<UserRow, 'is_active' | 'can_layer_1' | 'can_layer_2'>>) {
    setError(null)
    try {
      const updated = await api.updateUser(u.id, change)
      setUsers((all) => all.map((x) => (x.id === u.id ? updated : x)))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function resetPassword(u: UserRow) {
    const pw = window.prompt(`New password for ${u.email} (min 8 characters):`)
    if (!pw) return
    try {
      await api.resetPassword(u.id, pw)
      setSuccess(`Password reset for ${u.email}.`)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <h1>Users</h1>
      <Alert kind="error">{error}</Alert>
      <Alert kind="success">{success}</Alert>

      <form className="panel" onSubmit={onCreate}>
        <h2 style={{ marginTop: 0 }}>New annotator</h2>
        <div className="form-grid">
          <label className="field">
            Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            Initial password (min 8)
            <input type="text" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
        </div>
        <div className="row" style={{ marginTop: '0.75rem' }}>
          <label className="check">
            <input type="checkbox" checked={l1} onChange={(e) => setL1(e.target.checked)} /> Layer 1 (transcription)
          </label>
          <label className="check">
            <input type="checkbox" checked={l2} onChange={(e) => setL2(e.target.checked)} /> Layer 2 (scoring)
          </label>
          <div className="spacer" />
          <button className="primary" type="submit">
            Create annotator
          </button>
        </div>
      </form>

      <table className="data">
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Layer 1</th>
            <th>Layer 2</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const editable = u.role === 'annotator'
            return (
              <tr key={u.id} style={u.is_active ? undefined : { opacity: 0.55 }}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>
                  <input type="checkbox" aria-label={`Layer 1 for ${u.email}`} disabled={!editable} checked={u.can_layer_1} onChange={(e) => update(u, { can_layer_1: e.target.checked })} />
                </td>
                <td>
                  <input type="checkbox" aria-label={`Layer 2 for ${u.email}`} disabled={!editable} checked={u.can_layer_2} onChange={(e) => update(u, { can_layer_2: e.target.checked })} />
                </td>
                <td>
                  <input type="checkbox" aria-label={`Active ${u.email}`} disabled={!editable} checked={u.is_active} onChange={(e) => update(u, { is_active: e.target.checked })} />
                </td>
                <td>
                  {editable && (
                    <button className="small" onClick={() => resetPassword(u)}>
                      Reset password
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}
