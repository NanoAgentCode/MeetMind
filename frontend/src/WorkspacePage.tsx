import { AudioOutlined, CheckCircleFilled, EditOutlined, FileTextOutlined, LoadingOutlined, PlusOutlined, RobotOutlined, SafetyCertificateOutlined, UploadOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Tag, Upload } from 'antd'
import type { UploadFile } from 'antd'
import type { Meeting, Minutes } from './types'
import { formatDate } from './RecordsPage'

const { TextArea } = Input
const phases = [
  { key: 'uploaded', label: '录音已上传', icon: UploadOutlined },
  { key: 'transcribed', label: '语音已转写', icon: AudioOutlined },
  { key: 'generated', label: '纪要已生成', icon: RobotOutlined },
  { key: 'edited', label: '人工已定稿', icon: EditOutlined },
]
const rank: Record<string, number> = { uploaded: 0, queued: 0, transcribing: 0, transcription_failed: 0, transcribed: 1, generated: 2, edited: 3 }

interface WorkspacePageProps {
  meeting: Meeting | null
  draft: Minutes | null
  busy: string
  fileList: UploadFile[]
  title: string
  canCreate: boolean
  canManageMeetings: boolean
  onCreate: () => void
  onTitleChange: (title: string) => void
  onFileListChange: (files: UploadFile[]) => void
  onUpload: () => void
  onTranscribe: () => void
  onGenerate: () => void
  onSave: () => void
  onUpdate: (field: keyof Minutes, value: string) => void
}

export default function WorkspacePage({ meeting, draft, busy, fileList, title, canCreate, canManageMeetings, onCreate, onTitleChange, onFileListChange, onUpload, onTranscribe, onGenerate, onSave, onUpdate }: WorkspacePageProps) {
  const current = meeting ? rank[meeting.status] : -1
  const filename = fileList[0]?.name || ''
  return <>
    <div className="page-heading">
      <div><p className="breadcrumb">工作台&nbsp;&nbsp;/&nbsp;&nbsp;智能纪要</p><h1>{meeting ? meeting.title : '智能会议纪要'}</h1><p>{meeting ? `${meeting.filename} · ${formatDate(meeting.created_at)}` : '从会议录音中快速提炼共识、决策与行动事项'}</p></div>
      {meeting && <div className="meeting-heading-actions"><Tag className="meeting-tag" icon={<CheckCircleFilled />}>处理中</Tag>{canCreate && <Button icon={<PlusOutlined />} onClick={() => onCreate()}>新建会议</Button>}</div>}
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

    {!meeting && !canCreate ? <Empty description="当前账号没有创建会议权限" /> : !meeting ? (
      <section className="intake-grid">
        <article className="upload-panel">
          <div className="panel-heading"><div><span className="panel-icon"><PlusOutlined /></span><div><h2>创建会议任务</h2><p>上传录音，建立新的智能处理任务</p></div></div><Tag>单文件上传</Tag></div>
          <div className="form-block">
            <label htmlFor="meeting-title">会议名称</label>
            <Input id="meeting-title" value={title} onChange={(event) => onTitleChange(event.target.value)} placeholder="请输入会议名称，例如：产品研发周会" size="large" />
            <label>会议录音</label>
            <Upload.Dragger accept="audio/*,.mp3,.wav,.m4a,.webm,.mp4" maxCount={1} beforeUpload={() => false} fileList={fileList} onChange={({ fileList: next }) => onFileListChange(next)}>
              <div className="upload-illustration"><UploadOutlined /></div><p className="upload-title">点击或拖拽录音文件到此区域</p><p className="upload-hint">支持 MP3、WAV、M4A、WEBM、MP4，文件不超过 200 MB</p>
            </Upload.Dragger>
          </div>
          <div className="panel-footer"><span><SafetyCertificateOutlined /> 文件将加密存储于企业专属空间</span><Button type="primary" size="large" icon={<PlusOutlined />} onClick={onUpload} disabled={!filename} loading={busy === '上传'}>创建任务</Button></div>
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
            {canManageMeetings && (meeting.status === 'uploaded' || meeting.status === 'transcription_failed') && <Button type="primary" icon={<AudioOutlined />} onClick={() => onTranscribe()} loading={busy === '转写'}>{meeting.status === 'transcription_failed' ? '重试转写' : '开始转写'}</Button>}
            {(meeting.status === 'queued' || meeting.status === 'transcribing') && <Tag color="processing">{meeting.status === 'queued' ? '后台排队中' : '后台转写中'}</Tag>}
            {canManageMeetings && meeting.status === 'transcribed' && <Button type="primary" icon={<RobotOutlined />} onClick={() => onGenerate()} loading={busy === '生成纪要'}>生成纪要</Button>}
            {canManageMeetings && draft && <Button className="save-action" type="primary" icon={<EditOutlined />} onClick={onSave} loading={busy === '保存定稿'}><span>保存定稿<small>同步当前修改</small></span></Button>}
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
                <label>纪要标题</label><Input value={draft.title} onChange={(event) => onUpdate('title', event.target.value)} />
                <label>会议摘要</label><TextArea autoSize={{ minRows: 3 }} value={draft.summary} onChange={(event) => onUpdate('summary', event.target.value)} />
                <label>关键要点 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.key_points.join('\n')} onChange={(event) => onUpdate('key_points', event.target.value)} />
                <label>会议决策 <small>每行一项</small></label><TextArea autoSize={{ minRows: 2 }} value={draft.decisions.join('\n')} onChange={(event) => onUpdate('decisions', event.target.value)} />
                <label>行动事项 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.action_items.join('\n')} onChange={(event) => onUpdate('action_items', event.target.value)} />
              </div> : <Empty image={<FileTextOutlined />} description={meeting.transcript ? '转写完成，可以生成纪要' : '纪要将在转写后生成'} />}
            </div>
          </article>
        </div>
      </section>
    )}
  </>
}
