import { Navigate, Route, Routes } from 'react-router-dom'
import { homeFor, useAuth } from './components/AuthProvider'
import { Layout } from './components/Layout'
import { RoleGuard } from './components/RoleGuard'
import { AdminDashboard } from './pages/AdminDashboard'
import { AnnotatorQueue } from './pages/AnnotatorQueue'
import { Export } from './pages/Export'
import { Ingest } from './pages/Ingest'
import { Layer1 } from './pages/Layer1'
import { Layer2 } from './pages/Layer2'
import { Login } from './pages/Login'
import { Passages } from './pages/Passages'
import { Users } from './pages/Users'

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? homeFor(user) : '/login'} replace />
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RoleGuard role="admin">
            <Layout />
          </RoleGuard>
        }
      >
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/passages" element={<Passages />} />
        <Route path="/admin/ingest" element={<Ingest />} />
        <Route path="/admin/users" element={<Users />} />
        <Route path="/admin/export" element={<Export />} />
      </Route>
      <Route
        element={
          <RoleGuard role="annotator">
            <Layout />
          </RoleGuard>
        }
      >
        <Route path="/queue" element={<AnnotatorQueue />} />
        <Route path="/annotate/layer-1/:taskId" element={<Layer1 />} />
        <Route path="/annotate/layer-2/:taskId" element={<Layer2 />} />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
