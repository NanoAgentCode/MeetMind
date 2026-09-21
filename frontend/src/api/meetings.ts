import { api } from './client'
import type { ChatMessage, Meeting, Minutes } from '../types'

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

export function exportUrl(id: string, format: 'docx' | 'md') {
  return `/api/meetings/${id}/export?format=${format}`
}
