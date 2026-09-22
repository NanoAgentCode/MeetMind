// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import MeetingChat from './MeetingChat'
import { chat } from '../../api'

vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
vi.stubGlobal('matchMedia', () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }))

vi.mock('../../api', () => ({
  listMeetings: vi.fn().mockResolvedValue([]),
  listChatConversations: vi.fn().mockResolvedValue([{ id: 'saved-1', meeting_id: null, title: '之前的问题', updated_at: '2026-09-22T00:00:00Z', messages: [] }]),
  getChatConversation: vi.fn().mockResolvedValue({ id: 'saved-1', meeting_id: null, title: '之前的问题', updated_at: '2026-09-22T00:00:00Z', messages: [{ role: 'user', content: '之前的问题' }, { role: 'assistant', content: '之前的回答' }] }),
  chat: vi.fn().mockResolvedValue({ answer: '新的回答', conversation_id: 'saved-1' }),
}))

it('loads a saved conversation and continues it', async () => {
  render(<MeetingChat />)
  fireEvent.click(await screen.findByRole('button', { name: /之前的问题/ }))
  expect(await screen.findByText('之前的回答')).toBeInTheDocument()
  fireEvent.change(screen.getByPlaceholderText('输入问题，使用 @ 选择会议…'), { target: { value: '继续问' } })
  fireEvent.click(screen.getByRole('button', { name: '发送消息' }))
  expect(await screen.findByText('新的回答')).toBeInTheDocument()
  expect(chat).toHaveBeenCalledWith('继续问', [{ role: 'user', content: '之前的问题' }, { role: 'assistant', content: '之前的回答' }], undefined, 'saved-1')
})
