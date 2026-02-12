import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api'

export function useAdminGuard() {
  const navigate = useNavigate()
  const [admin, setAdmin] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const data = await api.getAdminMe()
        if (!cancelled) {
          setAdmin(data.admin)
        }
      } catch {
        if (!cancelled) {
          navigate('/admin/login')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    check()
    return () => {
      cancelled = true
    }
  }, [navigate])

  return { admin, loading }
}
