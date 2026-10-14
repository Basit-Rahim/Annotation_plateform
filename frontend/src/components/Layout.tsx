import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthProvider'

const ADMIN_LINKS = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/passages', label: 'Passages' },
  { to: '/admin/ingest', label: 'Ingest audio' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/export', label: 'Export' },
]

const ANNOTATOR_LINKS = [{ to: '/queue', label: 'My queue', end: true }]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const links = user?.role === 'admin' ? ADMIN_LINKS : ANNOTATOR_LINKS

  async function onLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Urdu Reading Annotation</div>
        <nav>
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <div>{user?.email}</div>
          <div className="muted small-text">{user?.role}</div>
          <button onClick={onLogout}>Log out</button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
