import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AppstoreOutlined, AudioOutlined, BellOutlined, CheckCircleFilled, CloudServerOutlined,
  EditOutlined, FileTextOutlined, FolderOpenOutlined, LoadingOutlined,
  LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined, MessageOutlined, PlusOutlined, RobotOutlined, SafetyCertificateOutlined,
  SettingOutlined, TeamOutlined, UploadOutlined,
} from '@ant-design/icons'
import { Button, Empty, Input, Modal, Popover, Spin, Tag, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { deleteMeeting, generateMinutes, getCurrentUser, getMeeting, listMeetings, listNotifications, login, logout, markNotificationRead, saveMinutes, transcribeMeeting, uploadRecording } from './api'
import type { AppNotification, Meeting, Minutes, User } from './types'
import MeetingChat from './MeetingChat'
import ModelManagement from './ModelManagement'
import AccessManagement from './AccessManagement'
import RecordsPage, { formatDate } from './RecordsPage'

const { TextArea } = Input
const phases = [
  { key: 'uploaded', label: '录音已上传', icon: UploadOutlined },
  { key: 'transcribed', label: '语音已转写', icon: AudioOutlined },
  { key: 'generated', label: '纪要已生成', icon: RobotOutlined },
  { key: 'edited', label: '人工已定稿', icon: EditOutlined },
]
const navigation = [
  { key: 'workspace', label: '工作台', icon: AppstoreOutlined },
  { key: 'records', label: '会议记录', icon: FolderOpenOutlined },
  { key: 'chat', label: '会议问答', icon: MessageOutlined },
  { key: 'templates', label: '纪要模板', icon: FileTextOutlined },
  { key: 'team', label: '团队空间', icon: TeamOutlined },
]
const rank: Record<string, number> = { uploaded: 0, queued: 0, transcribing: 0, transcription_failed: 0, transcribed: 1, generated: 2, edited: 3 }

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
  const [page, setPage] = useState<'workspace' | 'records' | 'chat' | 'models' | 'access'>('workspace')
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
  const current = meeting ? rank[meeting.status] : -1
  const filename = useMemo(() => fileList[0]?.name || '', [fileList])
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
    <div className={`app-layout${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand"><span className="brand-symbol">会</span><div><strong>会智录</strong><small>MEETMIND</small></div></div>
        <nav className="main-nav" aria-label="主导航">
          <p>协作空间</p>
          {navigation.map(({ key, label, icon: Icon }) => {
            const active = page === key
            const available = key === 'workspace' ? can('meeting:create') || canReadMeetings : key === 'records' ? canReadMeetings : key === 'chat' ? can('chat:use') : false
            return <button className={active ? 'active' : ''} key={key} type="button" disabled={!available} title={available ? label : `${label}（即将开放）`} onClick={() => available && (key === 'workspace' ? openWorkspace(meeting || undefined) : key === 'chat' ? openChat() : setPage('records'))}><Icon /><span className="nav-label">{label}</span>{active && <i />}</button>
          })}
          <p>系统管理</p>
          {(can('model:read') || can('model:manage')) && <button className={page === 'models' ? 'active' : ''} type="button" onClick={() => setPage('models')}><CloudServerOutlined /><span className="nav-label">模型服务</span>{page === 'models' && <i />}</button>}
          {canViewAccess && <button className={page === 'access' ? 'active' : ''} type="button" onClick={() => setPage('access')}><SafetyCertificateOutlined /><span className="nav-label">权限管理</span>{page === 'access' && <i />}</button>}
          <button type="button"><SettingOutlined /><span className="nav-label">系统设置</span></button>
        </nav>
        <div className="sidebar-footer">
          <div className="service-state"><span />服务运行正常</div>
          <button className="user-card" type="button" aria-label="退出登录" title="退出登录" onClick={confirmLogout}><span className="avatar">{user.display_name.slice(0, 1)}</span><div><strong>{user.display_name}</strong><small>{user.username}</small></div><LogoutOutlined className="logout-icon" /></button>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-title">
            <button
              className="sidebar-toggle"
              type="button"
              aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
              aria-expanded={!sidebarCollapsed}
              onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            >
              {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </button>
            <span>智能会议工作台</span>
          </div>
          <div className="topbar-actions"><span className="environment"><i />企业专属环境</span><Popover placement="bottomRight" trigger="click" content={<div className="notification-list"><div className="notification-title"><strong>站内通知</strong>{'Notification' in window && Notification.permission === 'default' && <Button size="small" onClick={() => void Notification.requestPermission()}>开启桌面提醒</Button>}</div>{notifications.length ? notifications.map((item) => <button className={item.read_at ? 'read' : ''} type="button" key={item.id} onClick={() => void openNotification(item)}><strong>{item.title}</strong><span>{item.body}</span><small>{formatDate(item.created_at)}</small></button>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" />}</div>}><button aria-label="通知" type="button"><BellOutlined />{notifications.some((item) => !item.read_at) && <b>{notifications.filter((item) => !item.read_at).length}</b>}</button></Popover></div>
        </header>

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
          /> : <>
          <div className="page-heading">
            <div><p className="breadcrumb">工作台&nbsp;&nbsp;/&nbsp;&nbsp;智能纪要</p><h1>{meeting ? meeting.title : '智能会议纪要'}</h1><p>{meeting ? `${meeting.filename} · ${formatDate(meeting.created_at)}` : '从会议录音中快速提炼共识、决策与行动事项'}</p></div>
            {meeting && <div className="meeting-heading-actions"><Tag className="meeting-tag" icon={<CheckCircleFilled />}>处理中</Tag>{can('meeting:create') && <Button icon={<PlusOutlined />} onClick={() => openWorkspace()}>新建会议</Button>}</div>}
          </div>

          <section className="progress-panel" aria-label="处理进度">
            <div className="progress-summary"><span>任务进度</span><strong>{Math.max(current + 1, 0)} / 4</strong></div>
            <div className="phase-track">
              {phases.map((phase, index) => {
                const Icon = phase.icon
                const done = index <= current
                const active = index === current + 1 || (current === 3 && index === 3)
                return <div className={`phase ${done ? 'done' : ''} ${active ? 'current' : ''}`} key={phase.key}><span className="phase-icon">{done ? <CheckCircleFilled /> : <Icon />}</span><div><small>步骤 {index + 1}</small><strong>{phase.label}</strong></div></div>
              })}
            </div>
          </section>

          {!meeting && !can('meeting:create') ? <Empty description="当前账号没有创建会议权限" /> : !meeting ? (
            <section className="intake-grid">
              <article className="upload-panel">
                <div className="panel-heading"><div><span className="panel-icon"><PlusOutlined /></span><div><h2>创建会议任务</h2><p>上传录音，建立新的智能处理任务</p></div></div><Tag>单文件上传</Tag></div>
                <div className="form-block">
                  <label htmlFor="meeting-title">会议名称</label>
                  <Input id="meeting-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="请输入会议名称，例如：产品研发周会" size="large" />
                  <label>会议录音</label>
                  <Upload.Dragger accept="audio/*,.mp3,.wav,.m4a,.webm,.mp4" maxCount={1} beforeUpload={() => false} fileList={fileList} onChange={({ fileList: next }) => setFileList(next)}>
                    <div className="upload-illustration"><UploadOutlined /></div><p className="upload-title">点击或拖拽录音文件到此区域</p><p className="upload-hint">支持 MP3、WAV、M4A、WEBM、MP4，文件不超过 200 MB</p>
                  </Upload.Dragger>
                </div>
                <div className="panel-footer"><span><SafetyCertificateOutlined /> 文件将加密存储于企业专属空间</span><Button type="primary" size="large" icon={<PlusOutlined />} onClick={handleUpload} disabled={!filename} loading={busy === '上传'}>创建任务</Button></div>
              </article>
              <aside className="guide-panel">
                <span className="guide-kicker">AI WORKFLOW</span><h2>一次上传，形成<br />结构化会议资产</h2><p>系统自动识别语音内容，并通过智能 Agent 整理为可协作、可追踪、可导出的会议纪要。</p>
                <ol><li><span>01</span><div><strong>精准转写</strong><small>还原会议完整上下文</small></div></li><li><span>02</span><div><strong>智能提炼</strong><small>自动识别要点与决策</small></div></li><li><span>03</span><div><strong>行动闭环</strong><small>整理待办并人工确认</small></div></li></ol>
              </aside>
            </section>
          ) : (
            <section className="workspace">
              <div className="workspace-toolbar">
                <div><strong>内容处理区</strong><span>请按任务进度完成处理与确认</span></div>
                <div className="actions workspace-actions">
                  {canManageMeetings && (meeting.status === 'uploaded' || meeting.status === 'transcription_failed') && <Button type="primary" icon={<AudioOutlined />} onClick={() => run('转写', () => transcribeMeeting(meeting.id))} loading={busy === '转写'}>{meeting.status === 'transcription_failed' ? '重试转写' : '开始转写'}</Button>}
                  {(meeting.status === 'queued' || meeting.status === 'transcribing') && <Tag color="processing">{meeting.status === 'queued' ? '后台排队中' : '后台转写中'}</Tag>}
                  {canManageMeetings && meeting.status === 'transcribed' && <Button type="primary" icon={<RobotOutlined />} onClick={() => run('生成纪要', () => generateMinutes(meeting.id))} loading={busy === '生成纪要'}>生成纪要</Button>}
                  {canManageMeetings && draft && <Button className="save-action" type="primary" icon={<EditOutlined />} onClick={handleSave} loading={busy === '保存定稿'}><span>保存定稿<small>同步当前修改</small></span></Button>}
                </div>
              </div>
              <div className="editor-grid">
                <article className="document-panel">
                  <div className="document-head"><div><span className="document-icon"><AudioOutlined /></span><div><h3>语音转写</h3><p>原始会议内容</p></div></div><Tag>只读</Tag></div>
                  <div className="document-body">{busy === '转写' || ['queued', 'transcribing'].includes(meeting.status) ? <div className="processing"><LoadingOutlined spin /><p>后台正在处理录音，完成后会发送通知…</p></div> : meeting.transcript ? <div className="transcript">{meeting.transcript}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={meeting.status === 'transcription_failed' ? '转写失败，请重试' : '等待开始转写'} />}</div>
                </article>
                <article className="document-panel minutes-panel">
                  <div className="document-head"><div><span className="document-icon ai"><RobotOutlined /></span><div><h3>智能纪要</h3><p>AI 生成 · 支持人工编辑</p></div></div>{draft && <Tag color="processing">可编辑</Tag>}</div>
                  <div className="document-body">
                    {busy === '生成纪要' ? <div className="processing"><LoadingOutlined spin /><p>Agent 正在提炼议题与行动项…</p></div> : draft ? <div className="minutes-form">
                      <label>纪要标题</label><Input value={draft.title} onChange={(event) => update('title', event.target.value)} />
                      <label>会议摘要</label><TextArea autoSize={{ minRows: 3 }} value={draft.summary} onChange={(event) => update('summary', event.target.value)} />
                      <label>关键要点 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.key_points.join('\n')} onChange={(event) => update('key_points', event.target.value)} />
                      <label>会议决策 <small>每行一项</small></label><TextArea autoSize={{ minRows: 2 }} value={draft.decisions.join('\n')} onChange={(event) => update('decisions', event.target.value)} />
                      <label>行动事项 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.action_items.join('\n')} onChange={(event) => update('action_items', event.target.value)} />
                    </div> : <Empty image={<FileTextOutlined />} description={meeting.transcript ? '转写完成，可以生成纪要' : '纪要将在转写后生成'} />}
                  </div>
                </article>
              </div>
            </section>
          )}
          </>}
        </main>
      </div>
    </div>
  )
}
