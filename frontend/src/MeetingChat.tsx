import { useEffect, useMemo, useState } from 'react'
import { AudioOutlined, CloseOutlined, MessageOutlined, PlusOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Spin, Tag, message } from 'antd'
import { chat, getChatConversation, listChatConversations, listMeetings } from './api'
import type { ChatConversation } from './api'
import type { ChatMessage, Meeting } from './types'

export default function MeetingChat({ initialMeeting = null, canBrowseMeetings = true }: { initialMeeting?: Meeting | null; canBrowseMeetings?: boolean }) {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(initialMeeting)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversations, setConversations] = useState<ChatConversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [meetingsLoading, setMeetingsLoading] = useState(true)
  const mentionIndex = input.lastIndexOf('@')
  const mentionOpen = mentionIndex >= 0
  const mentionTerm = mentionOpen ? input.slice(mentionIndex + 1).trim().toLowerCase() : ''
  const visibleMeetings = useMemo(() => meetings.filter((item) =>
    `${item.title} ${item.filename}`.toLowerCase().includes(mentionTerm)
  ), [meetings, mentionTerm])

  useEffect(() => {
    listChatConversations().then(setConversations).catch(() => message.error('对话历史加载失败'))
  }, [])

  useEffect(() => {
    if (!canBrowseMeetings) { setMeetingsLoading(false); return }
    listMeetings()
      .then(setMeetings)
      .catch(() => message.error('会议列表加载失败'))
      .finally(() => setMeetingsLoading(false))
  }, [canBrowseMeetings])

  useEffect(() => {
    if (!conversationId) return
    const active = conversations.find((item) => item.id === conversationId)
    if (active?.meeting_id) setSelectedMeeting(meetings.find((item) => item.id === active.meeting_id) || null)
  }, [meetings, conversations, conversationId])

  function chooseMeeting(item: Meeting) {
    setSelectedMeeting(item)
    setMessages([])
    setConversationId(null)
    setInput(input.slice(0, mentionIndex).trimStart())
  }

  function clearMeeting() {
    setSelectedMeeting(null)
    setMessages([])
    setConversationId(null)
  }

  function newConversation() {
    if (loading) return
    setConversationId(null)
    setSelectedMeeting(null)
    setMessages([])
    setInput('')
  }

  async function openConversation(id: string) {
    if (loading) return
    try {
      const conversation = await getChatConversation(id)
      setConversationId(id)
      setMessages(conversation.messages)
      setSelectedMeeting(meetings.find((item) => item.id === conversation.meeting_id) || null)
      setInput('')
    } catch {
      message.error('对话加载失败')
    }
  }

  async function send() {
    const question = input.trim()
    if (!question || loading) return
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: question }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      const result = await chat(question, messages.slice(-10), selectedMeeting?.id, conversationId || undefined)
      setMessages([...nextMessages, { role: 'assistant', content: result.answer }])
      setConversationId(result.conversation_id)
      try { setConversations(await listChatConversations()) } catch { message.error('对话历史刷新失败') }
    } catch (error) {
      setMessages(messages)
      setInput(question)
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || '对话失败，请检查模型服务配置')
    } finally {
      setLoading(false)
    }
  }

  return <div className="chat-page">
    <div className="page-heading chat-page-heading">
      <div><p className="breadcrumb">协作空间&nbsp;&nbsp;/&nbsp;&nbsp;会议问答</p><h1>会议问答</h1><p>直接提问，或通过 @ 关联一场会议后基于会议内容对话</p></div>
      <Tag color={selectedMeeting ? 'purple' : 'blue'}>{selectedMeeting ? '会议 RAG' : '普通问答'}</Tag>
    </div>
    <div className="chat-layout">
    <aside className="chat-history" aria-label="对话历史">
      <Button block icon={<PlusOutlined />} onClick={newConversation}>新对话</Button>
      <h2>对话历史</h2>
      {conversations.length ? conversations.map((item) => <button type="button" className={item.id === conversationId ? 'active' : ''} key={item.id} onClick={() => void openConversation(item.id)}><MessageOutlined /><span>{item.title}</span></button>) : <p>暂无对话记录</p>}
    </aside>
    <section className="chat-shell">
      <header className="chat-context">
        <div className={`chat-context-icon ${selectedMeeting ? 'rag' : ''}`}>{selectedMeeting ? <AudioOutlined /> : <MessageOutlined />}</div>
        <div><strong>{selectedMeeting?.title || '通用 AI 助手'}</strong><span>{selectedMeeting ? `${selectedMeeting.filename} · 仅依据本次会议内容回答` : '未关联会议，使用默认 LLM 进行普通问答'}</span></div>
        {selectedMeeting && <Button type="text" icon={<CloseOutlined />} aria-label="取消关联会议" onClick={clearMeeting}>取消关联</Button>}
      </header>
      <div className="chat-messages">
        {!messages.length && <div className="chat-empty"><span><RobotOutlined /></span><h2>{selectedMeeting ? '可以询问这场会议了' : '今天想了解什么？'}</h2><p>{selectedMeeting ? '我会根据会议转写与纪要回答，不确定的内容会明确说明。' : '在输入框键入 @ 可以选择会议，未选择时就是普通问答。'}</p></div>}
        {messages.map((item, index) => <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}><span>{item.role === 'assistant' ? 'AI' : '你'}</span><p>{item.content}</p></div>)}
        {loading && <div className="chat-message assistant"><span>AI</span><p><Spin size="small" /> 正在思考…</p></div>}
      </div>
      <footer className="chat-composer">
        {selectedMeeting && <div className="selected-meeting-chip"><AudioOutlined /><span>{selectedMeeting.title}</span><button type="button" aria-label="移除会议" onClick={clearMeeting}><CloseOutlined /></button></div>}
        <div className="composer-input">
          <Input.TextArea autoSize={{ minRows: 1, maxRows: 5 }} value={input} placeholder="输入问题，使用 @ 选择会议…" onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} />
          <Button type="primary" shape="circle" icon={<SendOutlined />} aria-label="发送消息" disabled={!input.trim()} loading={loading} onClick={() => void send()} />
        </div>
        {mentionOpen && <div className="meeting-mention-popover">
          <div className="mention-title"><span>@ 选择会议</span><small>{meetings.length} 场可用</small></div>
          <Spin spinning={meetingsLoading}>
            {visibleMeetings.length ? visibleMeetings.slice(0, 8).map((item) => <button type="button" key={item.id} onClick={() => chooseMeeting(item)}><span><AudioOutlined /></span><div><strong>{item.title}</strong><small>{item.filename}</small></div><Tag>{item.status === 'edited' ? '已完成' : '处理中'}</Tag></button>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的会议" />}
          </Spin>
        </div>}
        <small className="composer-hint">Enter 发送 · Shift + Enter 换行 · @ 关联会议</small>
      </footer>
    </section>
    </div>
  </div>
}
