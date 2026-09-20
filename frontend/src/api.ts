import axios from 'axios'
import type { Meeting, Minutes } from './types'

const api = axios.create({ baseURL: '/api', timeout: 120_000 })

export async function uploadRecording(file: File, title: string) {
  const body = new FormData()
  body.append('file', file)
  body.append('title', title)
  return (await api.post<Meeting>('/meetings', body)).data
}

export async function transcribeMeeting(id: string) {
  return (await api.post<Meeting>(`/meetings/${id}/transcribe`)).data
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

export function exportUrl(id: string, format: 'docx' | 'md') {
  return `/api/meetings/${id}/export?format=${format}`
}
