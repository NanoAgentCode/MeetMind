export type MeetingStatus = 'uploaded' | 'queued' | 'transcribing' | 'transcription_failed' | 'transcribed' | 'generated' | 'edited'

export interface User {
  id: string
  username: string
  display_name: string
  department_id: string | null
  is_active: boolean
  role_ids: string[]
  permissions: string[]
}

export interface Role { id: string; name: string; description: string; is_system: boolean; permissions: string[]; member_count: number }
export interface RoleInput { name: string; description: string; permissions: string[] }
export interface Department { id: string; name: string; parent_id: string | null; sort_order: number; member_count: number }
export interface DepartmentInput { name: string; parent_id: string | null; sort_order: number }
export interface UserCreateInput { username: string; display_name: string; password: string; department_id: string | null; role_ids: string[] }
export interface UserUpdateInput { display_name: string; password?: string; department_id: string | null; role_ids: string[]; is_active: boolean }
export interface PermissionItem { key: string; label: string }

export interface AppNotification {
  id: string
  user_id: string
  meeting_id: string | null
  title: string
  body: string
  created_at: string
  read_at: string | null
}

export interface Minutes {
  title: string
  summary: string
  key_points: string[]
  decisions: string[]
  action_items: string[]
}

export interface Meeting {
  id: string
  filename: string
  title: string
  created_at: string
  status: MeetingStatus
  owner_id?: string | null
  transcript: string
  minutes: Minutes | null
}

export type ProviderProtocol = 'openai' | 'anthropic' | 'ollama' | 'openai_compatible'
export type ModelType = 'llm' | 'rag' | 'asr'

export interface ModelProvider {
  id: string
  name: string
  protocol: ProviderProtocol
  base_url: string
  enabled: boolean
  api_key_configured: boolean
  api_key_masked: string
  created_at: string
}

export interface ModelProviderInput {
  name: string
  protocol: ProviderProtocol
  base_url: string
  api_key: string
  enabled: boolean
}

export interface ModelConfig {
  id: string
  provider_id: string
  name: string
  model_id: string
  model_type: ModelType
  enabled: boolean
  is_default: boolean
  created_at: string
}

export interface ModelConfigInput {
  provider_id: string
  name: string
  model_id: string
  model_type: ModelType
  enabled: boolean
  is_default: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
