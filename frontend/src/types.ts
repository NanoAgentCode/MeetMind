export type MeetingStatus = 'uploaded' | 'transcribed' | 'generated' | 'edited'

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
  transcript: string
  minutes: Minutes | null
}

