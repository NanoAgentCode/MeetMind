import { api } from './client'
import type { AppNotification, User } from '../types'

export async function login(username: string, password: string) {
  return (await api.post<User>('/auth/login', { username, password })).data
}

export async function getCurrentUser() {
  return (await api.get<User>('/auth/me')).data
}

export async function logout() {
  await api.post('/auth/logout')
}

export async function listNotifications() {
  return (await api.get<AppNotification[]>('/notifications')).data
}

export async function markNotificationRead(id: string) {
  await api.post(`/notifications/${id}/read`)
}
