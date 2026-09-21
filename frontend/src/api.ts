import axios from 'axios'
import type { Meeting, Minutes, ModelConfig, ModelConfigInput, ModelProvider, ModelProviderInput } from './types'

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

export async function askMeeting(id: string, question: string) {
  return (await api.post<{ answer: string }>(`/meetings/${id}/questions`, { question })).data.answer
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
