import { api } from './client'
import type { ModelConfig, ModelConfigInput, ModelProvider, ModelProviderInput } from '../shared/types'

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
