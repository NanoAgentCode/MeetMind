import { useEffect, useState } from 'react'
import { message } from 'antd'
import { getCurrentUser, login, logout } from '../../api'
import type { User } from '../../shared/types'

export function useSession() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [loginBusy, setLoginBusy] = useState(false)

  useEffect(() => {
    void getCurrentUser().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false))
    const unauthorized = () => setUser(null)
    window.addEventListener('meetmind:unauthorized', unauthorized)
    return () => window.removeEventListener('meetmind:unauthorized', unauthorized)
  }, [])

  async function signIn(username: string, password: string) {
    setLoginBusy(true)
    try {
      setUser(await login(username, password))
      message.success('登录成功')
      return true
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || '登录失败')
      return false
    } finally {
      setLoginBusy(false)
    }
  }

  async function signOut() {
    await logout()
    setUser(null)
  }

  return { user, setUser, loading, loginBusy, signIn, signOut }
}
