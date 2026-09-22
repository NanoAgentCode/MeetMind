import { useEffect, useRef, useState } from 'react'
import { listNotifications, markNotificationRead } from '../../api'
import type { AppNotification, User } from '../../shared/types'

export function useNotifications(user: User | null) {
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const seenIds = useRef<Set<string> | null>(null)

  useEffect(() => {
    if (!user) {
      setNotifications([])
      seenIds.current = null
      return
    }
    let active = true
    async function refresh() {
      try {
        const latest = await listNotifications()
        if (!active) return
        const previous = seenIds.current
        if (previous && 'Notification' in window && Notification.permission === 'granted') {
          latest.filter((item) => !item.read_at && !previous.has(item.id)).forEach((item) => {
            new Notification(item.title, { body: item.body })
          })
        }
        seenIds.current = new Set(latest.map((item) => item.id))
        setNotifications(latest)
      } catch { /* Notification polling should not interrupt the workspace. */ }
    }
    void refresh()
    const timer = window.setInterval(refresh, 10_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [user])

  async function markRead(item: AppNotification) {
    await markNotificationRead(item.id)
    setNotifications((current) => current.map((entry) => entry.id === item.id ? { ...entry, read_at: new Date().toISOString() } : entry))
  }

  return { notifications, markRead }
}
