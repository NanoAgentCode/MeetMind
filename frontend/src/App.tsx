import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Input, Modal, Spin, message } from 'antd'
import type { UploadFile } from 'antd'
import { deleteMeeting, generateMinutes, getCurrentUser, getMeeting, listMeetings, listNotifications, login, logout, markNotificationRead, saveMinutes, transcribeMeeting, uploadRecording } from './api'
import type { AppNotification, Meeting, Minutes, User } from './types'
import MeetingChat from './MeetingChat'
import ModelManagement from './ModelManagement'
import AccessManagement from './AccessManagement'
import RecordsPage from './RecordsPage'
import WorkspacePage from './WorkspacePage'
import AppChrome from './AppChrome'
import type { Page } from './AppChrome'


function lines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginBusy, setLoginBusy] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const seenNotificationIds = useRef<Set<string> | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [page, setPage] = useState<Page>('workspace')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [title, setTitle] = useState('')
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [chatMeeting, setChatMeeting] = useState<Meeting | null>(null)
  const [draft, setDraft] = useState<Minutes | null>(null)
  const [busy, setBusy] = useState('')
  const [records, setRecords] = useState<Meeting[]>([])
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [recordsLoaded, setRecordsLoaded] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const can = (permission: string) => !!user?.permissions.includes(permission)
  const canReadMeetings = ['meeting:read_own', 'meeting:read_department', 'meeting:read_all', 'meeting:manage_own', 'meeting:manage_department', 'meeting:manage_all'].some(can)
  const canManageMeetings = ['meeting:manage_own', 'meeting:manage_department', 'meeting:manage_all'].some(can)
  const canViewAccess = ['user:read', 'user:manage', 'role:read', 'role:manage', 'department:read', 'department:manage'].some(can)

  useEffect(() => {
    if (!user) return
    if (page === 'workspace' && !meeting && !can('meeting:create')) {
      if (canReadMeetings) setPage('records')
      else if (can('chat:use')) setPage('chat')
      else if (can('model:read') || can('model:manage')) setPage('models')
      else if (canViewAccess) setPage('access')
    } else if (page === 'access' && !canViewAccess) setPage('workspace')
  }, [user, page, meeting, canReadMeetings, canViewAccess])
  const visibleRecords = useMemo(() => records.filter((item) => {
    const matchesQuery = `${item.title} ${item.filename}`.toLowerCase().includes(query.trim().toLowerCase())
    return matchesQuery && (statusFilter === 'all' || item.status === statusFilter)
  }), [query, records, statusFilter])

  useEffect(() => {
    void getCurrentUser().then(setUser).catch(() => setUser(null)).finally(() => setAuthLoading(false))
  }, [])

  useEffect(() => {
    const resetSession = () => {
      setUser(null)
      setMeeting(null)
      setRecords([])
      setRecordsLoaded(false)
      setNotifications([])
      seenNotificationIds.current = null
    }
    window.addEventListener('meetmind:unauthorized', resetSession)
    return () => window.removeEventListener('meetmind:unauthorized', resetSession)
  }, [])

  useEffect(() => {
    if (!user) return
    let active = true
    async function refresh() {
      try {
        const latest = await listNotifications()
        if (!active) return
        const previous = seenNotificationIds.current
        if (previous && 'Notification' in window && Notification.permission === 'granted') {
          latest.filter((item) => !item.read_at && !previous.has(item.id)).forEach((item) => {
            new Notification(item.title, { body: item.body })
          })
        }
        seenNotificationIds.current = new Set(latest.map((item) => item.id))
        setNotifications(latest)
      } catch { /* Notification polling should not interrupt the workspace. */ }
    }
    void refresh()
    const timer = window.setInterval(refresh, 10_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [user])

  useEffect(() => {
    if (!user || !meeting || !['queued', 'transcribing'].includes(meeting.status)) return
    const timer = window.setInterval(async () => {
      try {
        const latest = await getMeeting(meeting.id)
        setMeeting(latest)
        setRecords((current) => current.map((item) => item.id === latest.id ? latest : item))
      } catch { /* Keep the current view until the user refreshes. */ }
    }, 5_000)
    return () => window.clearInterval(timer)
  }, [user, meeting])

  async function handleLogin() {
    setLoginBusy(true)
    try {
      setUser(await login(username.trim(), password))
      setPassword('')
      message.success('登录成功')
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || '登录失败')
    } finally {
      setLoginBusy(false)
    }
  }

  async function handleLogout() {
    await logout()
    setUser(null)
    setMeeting(null)
    setRecords([])
    setRecordsLoaded(false)
    setNotifications([])
    seenNotificationIds.current = null
  }

  function confirmLogout() {
    Modal.confirm({
      title: '确认退出登录？',
      content: '退出后需要重新输入账号和密码才能访问工作台。',
      okText: '退出登录',
      cancelText: '取消',
      onOk: handleLogout,
    })
  }

  async function openNotification(item: AppNotification) {
    await markNotificationRead(item.id)
    setNotifications((current) => current.map((entry) => entry.id === item.id ? { ...entry, read_at: new Date().toISOString() } : entry))
    if (item.meeting_id) {
      try { openWorkspace(await getMeeting(item.meeting_id)) } catch { message.error('会议已不存在') }
    }
  }

  async function loadRecords() {
    setRecordsLoading(true)
    try {
      setRecords(await listMeetings())
      setRecordsLoaded(true)
    } catch {
      message.error('会议记录加载失败，请检查后端和 RustFS 服务')
    } finally {
      setRecordsLoading(false)
    }
  }

  useEffect(() => {
    if (page === 'records' && !recordsLoaded) void loadRecords()
  }, [page, recordsLoaded])

  function openWorkspace(item?: Meeting) {
    setMeeting(item || null)
    setDraft(item?.minutes || null)
    if (!item) {
      setTitle('')
      setFileList([])
    }
    setPage('workspace')
  }

  function openRecord(item: Meeting) {
    openWorkspace(item)
  }

  function openChat(item?: Meeting) {
    setChatMeeting(item || null)
    setPage('chat')
  }

  function confirmDelete(item: Meeting) {
    Modal.confirm({
      title: '删除会议记录？',
      content: `“${item.title}”的录音、纪要和导出文件将一并删除，此操作无法撤销。`,
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        await deleteMeeting(item.id)
        setRecords((current) => current.filter((record) => record.id !== item.id))
        if (meeting?.id === item.id) {
          setMeeting(null)
          setDraft(null)
        }
        message.success('会议记录已删除')
      },
    })
  }

  async function run(label: string, action: () => Promise<Meeting>) {
    setBusy(label)
    try {
      const result = await action()
      setMeeting(result)
      setRecords((current) => {
        const rest = current.filter((item) => item.id !== result.id)
        return [result, ...rest]
      })
      if (result.minutes) setDraft(result.minutes)
      message.success(`${label}完成`)
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || `${label}失败，请检查后端服务`)
    } finally {
      setBusy('')
    }
  }

  async function handleUpload() {
    const raw = fileList[0]?.originFileObj
    if (!raw) return message.warning('请先选择录音文件')
    await run('上传', () => uploadRecording(raw, title.trim() || raw.name.replace(/\.[^.]+$/, '')))
  }

  async function handleSave() {
    if (!meeting || !draft) return
    await run('保存定稿', () => saveMinutes(meeting.id, draft))
  }

  function update(field: keyof Minutes, value: string) {
    if (!draft) return
    setDraft({ ...draft, [field]: field === 'title' || field === 'summary' ? value : lines(value) })
  }

  if (authLoading) return <div className="auth-loading"><Spin size="large" /></div>
  if (!user) return <div className="login-page"><div className="login-brand"><span className="brand-symbol">会</span><strong>会智录</strong><small>MEETMIND</small></div><section className="login-card"><p className="login-eyebrow">企业会议工作空间</p><h1>欢迎回来</h1><p>登录后继续处理录音、纪要与会议问答</p><form onSubmit={(event) => { event.preventDefault(); void handleLogin() }}><label htmlFor="login-username">账号</label><Input id="login-username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="请输入账号" /><label htmlFor="login-password">密码</label><Input.Password id="login-password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="请输入密码" /><Button type="primary" htmlType="submit" loading={loginBusy} disabled={!username.trim() || !password}>登录工作台</Button></form></section><span className="login-footnote">安全协作 · 会议内容仅对账号所属用户可见</span></div>

  return (
    <AppChrome user={user} page={page} meeting={meeting} notifications={notifications}
      sidebarCollapsed={sidebarCollapsed} can={can} canReadMeetings={canReadMeetings} canViewAccess={canViewAccess}
      onPageChange={setPage} onOpenWorkspace={openWorkspace} onOpenChat={() => openChat()}
      onLogout={confirmLogout} onOpenNotification={(item) => void openNotification(item)}
      onToggleSidebar={() => setSidebarCollapsed((collapsed) => !collapsed)}>
        <main className="content">
          {page === 'access' ? <AccessManagement currentUser={user} onPermissionsChanged={() => void getCurrentUser().then(setUser)} /> : page === 'models' ? <ModelManagement canManage={can('model:manage')} /> : page === 'chat' ? <MeetingChat initialMeeting={chatMeeting} canBrowseMeetings={canReadMeetings} /> : page === 'records' ? <RecordsPage
            records={records}
            visibleRecords={visibleRecords}
            loading={recordsLoading}
            query={query}
            statusFilter={statusFilter}
            onQueryChange={setQuery}
            onStatusChange={setStatusFilter}
            onRefresh={loadRecords}
            onOpen={openRecord}
            onChat={openChat}
            onDelete={confirmDelete}
            onCreate={() => openWorkspace()}
            canCreate={can('meeting:create')}
            canChat={can('chat:use')}
            canManage={canManageMeetings}
          /> :
          <WorkspacePage meeting={meeting} draft={draft} busy={busy} fileList={fileList} title={title}
            canCreate={can('meeting:create')} canManageMeetings={canManageMeetings}
            onCreate={() => openWorkspace()} onTitleChange={setTitle} onFileListChange={setFileList}
            onUpload={handleUpload} onTranscribe={() => meeting && void run('转写', () => transcribeMeeting(meeting.id))}
            onGenerate={() => meeting && void run('生成纪要', () => generateMinutes(meeting.id))}
            onSave={handleSave} onUpdate={update} />}
        </main>
    </AppChrome>
  )
}
