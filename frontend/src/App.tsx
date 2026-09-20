import { useEffect, useMemo, useState } from 'react'
import {
  AppstoreOutlined, AudioOutlined, BellOutlined, CheckCircleFilled, CloudServerOutlined,
  DeleteOutlined, DownloadOutlined, EditOutlined, FileTextOutlined, FolderOpenOutlined, LoadingOutlined,
  MenuFoldOutlined, MoreOutlined, PlusOutlined, RobotOutlined, SafetyCertificateOutlined,
  SearchOutlined, SettingOutlined, TeamOutlined, UploadOutlined,
} from '@ant-design/icons'
import { Button, Empty, Input, Modal, Select, Spin, Table, Tag, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { deleteMeeting, exportUrl, generateMinutes, listMeetings, saveMinutes, transcribeMeeting, uploadRecording } from './api'
import type { Meeting, Minutes } from './types'

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
  { key: 'templates', label: '纪要模板', icon: FileTextOutlined },
  { key: 'team', label: '团队空间', icon: TeamOutlined },
]
const rank: Record<string, number> = { uploaded: 0, transcribed: 1, generated: 2, edited: 3 }
const statusMeta = {
  uploaded: { label: '待转写', color: 'default' },
  transcribed: { label: '待生成', color: 'processing' },
  generated: { label: '待定稿', color: 'warning' },
  edited: { label: '已完成', color: 'success' },
} as const

function lines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

function formatDate(value?: string) {
  if (!value) return '刚刚创建'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

function RecordsPage({
  records, visibleRecords, loading, query, statusFilter, onQueryChange,
  onStatusChange, onRefresh, onOpen, onDelete, onCreate,
}: {
  records: Meeting[]
  visibleRecords: Meeting[]
  loading: boolean
  query: string
  statusFilter: string
  onQueryChange: (value: string) => void
  onStatusChange: (value: string) => void
  onRefresh: () => void
  onOpen: (meeting: Meeting) => void
  onDelete: (meeting: Meeting) => void
  onCreate: () => void
}) {
  const completed = records.filter((item) => item.status === 'edited').length
  const processing = records.length - completed
  const columns = [
    {
      title: '会议名称', dataIndex: 'title', key: 'title',
      render: (_: string, item: Meeting) => <button className="record-title" type="button" onClick={() => onOpen(item)}><span><AudioOutlined /></span><div><strong>{item.title}</strong><small>{item.filename}</small></div></button>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (value: string) => <span className="table-secondary">{formatDate(value)}</span>,
    },
    {
      title: '处理状态', dataIndex: 'status', key: 'status', width: 120,
      render: (value: Meeting['status']) => <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag>,
    },
    {
      title: '内容概况', key: 'content', width: 190,
      render: (_: unknown, item: Meeting) => <span className="table-secondary">{item.transcript ? `${item.transcript.length} 字转写` : '暂无转写'}{item.minutes ? ' · 已有纪要' : ''}</span>,
    },
    {
      title: '操作', key: 'actions', width: 150, align: 'right' as const,
      render: (_: unknown, item: Meeting) => <div className="record-actions"><Button type="link" onClick={() => onOpen(item)}>打开</Button><Button type="text" danger icon={<DeleteOutlined />} aria-label={`删除${item.title}`} onClick={() => onDelete(item)} /></div>,
    },
  ]

  return <>
    <div className="page-heading records-heading">
      <div><p className="breadcrumb">工作台&nbsp;&nbsp;/&nbsp;&nbsp;会议记录</p><h1>会议记录</h1><p>统一管理会议录音、转写内容与会议纪要</p></div>
      <Button type="primary" size="large" icon={<PlusOutlined />} onClick={onCreate}>新建会议</Button>
    </div>
    <section className="record-stats">
      <div><span className="stat-icon blue"><FolderOpenOutlined /></span><div><small>全部会议</small><strong>{records.length}</strong></div></div>
      <div><span className="stat-icon amber"><LoadingOutlined /></span><div><small>处理中</small><strong>{processing}</strong></div></div>
      <div><span className="stat-icon green"><CheckCircleFilled /></span><div><small>已完成</small><strong>{completed}</strong></div></div>
      <div><span className="stat-icon violet"><RobotOutlined /></span><div><small>纪要生成率</small><strong>{records.length ? Math.round(records.filter((item) => item.minutes).length / records.length * 100) : 0}%</strong></div></div>
    </section>
    <section className="records-panel">
      <div className="records-toolbar">
        <div><Input allowClear prefix={<SearchOutlined />} placeholder="搜索会议名称或文件名" value={query} onChange={(event) => onQueryChange(event.target.value)} /><Select value={statusFilter} onChange={onStatusChange} options={[{ value: 'all', label: '全部状态' }, ...Object.entries(statusMeta).map(([value, meta]) => ({ value, label: meta.label }))]} /></div>
        <Button onClick={onRefresh} loading={loading}>刷新</Button>
      </div>
      <Spin spinning={loading}>
        <Table<Meeting> rowKey="id" columns={columns} dataSource={visibleRecords} pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 条记录` }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={query || statusFilter !== 'all' ? '没有符合条件的会议记录' : '暂无会议记录'}><Button type="primary" onClick={onCreate}>创建第一场会议</Button></Empty> }} />
      </Spin>
    </section>
  </>
}

export default function App() {
  const [page, setPage] = useState<'workspace' | 'records'>('workspace')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [title, setTitle] = useState('')
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [draft, setDraft] = useState<Minutes | null>(null)
  const [busy, setBusy] = useState('')
  const [records, setRecords] = useState<Meeting[]>([])
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [recordsLoaded, setRecordsLoaded] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const current = meeting ? rank[meeting.status] : -1
  const filename = useMemo(() => fileList[0]?.name || '', [fileList])
  const visibleRecords = useMemo(() => records.filter((item) => {
    const matchesQuery = `${item.title} ${item.filename}`.toLowerCase().includes(query.trim().toLowerCase())
    return matchesQuery && (statusFilter === 'all' || item.status === statusFilter)
  }), [query, records, statusFilter])

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

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand"><span className="brand-symbol">会</span><div><strong>会智录</strong><small>MEETMIND</small></div></div>
        <nav className="main-nav" aria-label="主导航">
          <p>协作空间</p>
          {navigation.map(({ key, label, icon: Icon }) => {
            const active = page === key
            const available = key === 'workspace' || key === 'records'
            return <button className={active ? 'active' : ''} key={key} type="button" disabled={!available} title={available ? label : `${label}（即将开放）`} onClick={() => available && (key === 'workspace' ? openWorkspace(meeting || undefined) : setPage('records'))}><Icon /><span>{label}</span>{active && <i />}</button>
          })}
          <p>系统管理</p>
          <button type="button"><CloudServerOutlined /><span>模型服务</span></button>
          <button type="button"><SafetyCertificateOutlined /><span>权限管理</span></button>
          <button type="button"><SettingOutlined /><span>系统设置</span></button>
        </nav>
        <div className="sidebar-footer">
          <div className="service-state"><span />服务运行正常</div>
          <div className="user-card"><span className="avatar">管</span><div><strong>系统管理员</strong><small>企业工作空间</small></div><MoreOutlined /></div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-title"><MenuFoldOutlined /><span>智能会议工作台</span></div>
          <div className="topbar-actions"><span className="environment"><i />企业专属环境</span><button aria-label="通知" type="button"><BellOutlined /><b>2</b></button></div>
        </header>

        <main className="content">
          {page === 'records' ? <RecordsPage
            records={records}
            visibleRecords={visibleRecords}
            loading={recordsLoading}
            query={query}
            statusFilter={statusFilter}
            onQueryChange={setQuery}
            onStatusChange={setStatusFilter}
            onRefresh={loadRecords}
            onOpen={openRecord}
            onDelete={confirmDelete}
            onCreate={() => openWorkspace()}
          /> : <>
          <div className="page-heading">
            <div><p className="breadcrumb">工作台&nbsp;&nbsp;/&nbsp;&nbsp;智能纪要</p><h1>{meeting ? meeting.title : '智能会议纪要'}</h1><p>{meeting ? `${meeting.filename} · ${formatDate(meeting.created_at)}` : '从会议录音中快速提炼共识、决策与行动事项'}</p></div>
            {meeting && <Tag className="meeting-tag" icon={<CheckCircleFilled />}>处理中</Tag>}
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

          {!meeting ? (
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
                <div className="actions">
                  {meeting.status === 'uploaded' && <Button type="primary" icon={<AudioOutlined />} onClick={() => run('转写', () => transcribeMeeting(meeting.id))} loading={busy === '转写'}>开始转写</Button>}
                  {meeting.status === 'transcribed' && <Button type="primary" icon={<RobotOutlined />} onClick={() => run('生成纪要', () => generateMinutes(meeting.id))} loading={busy === '生成纪要'}>生成纪要</Button>}
                  {draft && <Button type="primary" icon={<EditOutlined />} onClick={handleSave} loading={busy === '保存定稿'}>保存定稿</Button>}
                  {meeting.status === 'edited' && <><Button icon={<DownloadOutlined />} href={exportUrl(meeting.id, 'docx')}>导出 Word</Button><Button icon={<DownloadOutlined />} href={exportUrl(meeting.id, 'md')}>Markdown</Button></>}
                </div>
              </div>
              <div className="editor-grid">
                <article className="document-panel">
                  <div className="document-head"><div><span className="document-icon"><AudioOutlined /></span><div><h3>语音转写</h3><p>原始会议内容</p></div></div><Tag>只读</Tag></div>
                  <div className="document-body">{busy === '转写' ? <div className="processing"><LoadingOutlined spin /><p>正在识别录音内容…</p></div> : meeting.transcript ? <div className="transcript">{meeting.transcript}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="等待开始转写" />}</div>
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
