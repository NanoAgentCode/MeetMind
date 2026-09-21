import axios from 'axios'
import type { AppNotification, ChatMessage, Meeting, Minutes, ModelConfig, ModelConfigInput, ModelProvider, ModelProviderInput, User } from './types'

const api = axios.create({ baseURL: '/api', timeout: 120_000 })
api.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401 && error.config?.url !== '/auth/login') {
    window.dispatchEvent(new Event('meetmind:unauthorized'))
  }
  return Promise.reject(error)
})

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

export async function uploadRecording(file: File, title: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('title', title)
  return (await api.post<Meeting>('/meetings', body, { timeout: 600_000 })).data
}

export async function transcribeMeeting(id: string) {
  return (await api.post<Meeting>(`/meetings/${id}/transcribe`, undefined, { timeout: 240_000 })).data
}

export async function generateMinutes(id: string) {
  return (await api.post<Meeting>(`/meetings/${id}/minutes/generate`)).data
}

export async function saveMinutes(id: string, minutes: Minutes) {
  return (await api.put<Meeting>(`/meetings/${id}/minutes`, minutes)).data
}

export async function getMeeting(id: string) {
  return (await api.get<Meeting>(`/meetings/${id}`)).data
}

export async function listMeetings() {
  return (await api.get<Meeting[]>('/meetings')).data
}

export async function deleteMeeting(id: string) {
  await api.delete(`/meetings/${id}`)
}

export async function askMeeting(id: string, question: string) {
  return (await api.post<{ answer: string }>(`/meetings/${id}/questions`, { question })).data.answer
}

export async function chat(question: string, history: ChatMessage[], meetingId?: string) {
  return (await api.post<{ answer: string }>('/chat', {
    question, history, meeting_id: meetingId || null,
  })).data.answer
}

export async function listModelProviders() {
  return (await api.get<ModelProvider[]>('/model-providers')).data
}

export async function createModelProvider(data: ModelProviderInput) {
  return (await api.post<ModelProvider>('/model-providers', data)).data
}

export async function updateModelProvider(id: string, data: ModelProviderInput) {
  return (await api.put<ModelProvider>(`/model-providers/${id}`, data)).data
}

export async function deleteModelProvider(id: string) {
  await api.delete(`/model-providers/${id}`)
}

export async function testModelProvider(id: string) {
  return (await api.post<{ message: string }>(`/model-providers/${id}/test`)).data
}

export async function listProviderModels(id: string) {
  return (await api.get<{ models: string[] }>(`/model-providers/${id}/models`)).data.models
}

export async function listModelConfigs() {
  return (await api.get<ModelConfig[]>('/model-configs')).data
}

export async function createModelConfig(data: ModelConfigInput) {
  return (await api.post<ModelConfig>('/model-configs', data)).data
}

export async function updateModelConfig(id: string, data: ModelConfigInput) {
  return (await api.put<ModelConfig>(`/model-configs/${id}`, data)).data
}

export async function deleteModelConfig(id: string) {
  await api.delete(`/model-configs/${id}`)
}

export function exportUrl(id: string, format: 'docx' | 'md') {
  return `/api/meetings/${id}/export?format=${format}`
}
