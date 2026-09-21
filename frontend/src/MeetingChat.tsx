import { useEffect, useMemo, useState } from 'react'
import { AudioOutlined, CloseOutlined, MessageOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Spin, Tag, message } from 'antd'
import { chat, listMeetings } from './api'
import type { ChatMessage, Meeting } from './types'

export default function MeetingChat() {
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
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
    listMeetings()
      .then(setMeetings)
      .catch(() => message.error('会议列表加载失败'))
      .finally(() => setMeetingsLoading(false))
  }, [])

  function chooseMeeting(item: Meeting) {
    setSelectedMeeting(item)
    setMessages([])
    setInput(input.slice(0, mentionIndex).trimStart())
  }

  function clearMeeting() {
    setSelectedMeeting(null)
    setMessages([])
  }

  async function send() {
    const question = input.trim()
    if (!question || loading) return
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: question }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    try {
      const answer = await chat(question, messages.slice(-10), selectedMeeting?.id)
      setMessages([...nextMessages, { role: 'assistant', content: answer }])
    } catch (error) {
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
}
