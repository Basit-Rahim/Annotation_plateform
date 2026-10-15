import { useEffect, useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { Layer, Task } from '../api/types'

const POLL_MS = 20_000

/**
 * Load the annotator's checkout for a workspace and keep polling so the page
 * notices when the task is withdrawn by an admin or the lease expires.
 */
export function useWorkspaceTask(taskId: string | undefined, layer: Layer) {
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [lost, setLost] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function check(initial: boolean) {
      try {
        const current = await api.currentTask()
        if (cancelled) return
        if (current && current.id === taskId && current.layer === layer) {
          if (initial) setTask(current)
          else setTask((t) => (t ? { ...t, lease_expires_at: current.lease_expires_at } : current))
          setLost(null)
        } else {
          setLost(
            initial
              ? 'This task is not checked out to you.'
              : 'This task is no longer checked out to you: it was withdrawn by an admin or your lease expired. Your work so far is saved; if the task is still in the pool, Take next gives it back to you first.',
          )
        }
      } catch (err) {
        if (!cancelled && initial) setLost(errorMessage(err))
      } finally {
        if (!cancelled && initial) setLoading(false)
      }
    }

    void check(true)
    const timer = window.setInterval(() => void check(false), POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [taskId, layer])

  return { task, loading, lost }
}
