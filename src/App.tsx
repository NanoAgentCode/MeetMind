import { useMemo, useState } from 'react'
import {
  AudioOutlined,
  CheckCircleFilled,
  DownloadOutlined,
  EditOutlined,
  FileTextOutlined,
  LoadingOutlined,
  RobotOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { Button, Empty, Input, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import {
  exportUrl,
  generateMinutes,
  saveMinutes,
  transcribeMeeting,
  uploadRecording,
} from './api'
import type { Meeting, Minutes } from './types'

const { TextArea } = Input

const phases = [
  { key: 'uploaded', label: '录音上传', icon: UploadOutlined },
  { key: 'transcribed', label: '语音转写', icon: AudioOutlined },
  { key: 'generated', label: '生成纪要', icon: RobotOutlined },
  { key: 'edited', label: '人工定稿', icon: EditOutlined },
]

const rank: Record<string, number> = { uploaded: 0, transcribed: 1, generated: 2, edited: 3 }

function lines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

export default function App() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [title, setTitle] = useState('')
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [draft, setDraft] = useState<Minutes | null>(null)
  const [busy, setBusy] = useState('')

  const current = meeting ? rank[meeting.status] : -1
  const filename = useMemo(() => fileList[0]?.name || '', [fileList])

  async function run(label: string, action: () => Promise<Meeting>) {
    setBusy(label)
    try {
      const result = await action()
      setMeeting(result)
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
    <main className="app-shell">
      <header className="masthead">
        <div className="brand-mark"><span>会</span></div>
        <div>
          <p className="eyebrow">MEETING INTELLIGENCE STUDIO</p>
          <h1>会智录</h1>
        </div>
        <div className="masthead-note">让讨论留下结论<br />让结论变成行动</div>
      </header>

      <section className="phase-track" aria-label="处理进度">
        {phases.map((phase, index) => {
          const Icon = phase.icon
          const done = index <= current
          return (
            <div className={`phase ${done ? 'done' : ''}`} key={phase.key}>
              <span>{done ? <CheckCircleFilled /> : <Icon />}</span>
              <div><small>0{index + 1}</small><strong>{phase.label}</strong></div>
            </div>
          )
        })}
      </section>

      {!meeting ? (
        <section className="upload-stage">
          <div className="stage-copy">
            <p className="section-number">第一阶段 · 会后整理</p>
            <h2>把一场会议，<br /><em>整理成可执行的共识。</em></h2>
            <p>上传录音后，系统将完成语音转写、要点归纳与行动项提取。所有结果都可人工修改，再导出为正式文档。</p>
            <div className="format-list"><span>MP3</span><span>WAV</span><span>M4A</span><span>WEBM</span></div>
          </div>
          <div className="upload-card">
            <label>会议名称</label>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：产品周会 · 九月第三周" size="large" />
            <label>会议录音</label>
            <Upload.Dragger
              accept="audio/*,.mp3,.wav,.m4a,.webm,.mp4"
              maxCount={1}
              beforeUpload={() => false}
              fileList={fileList}
              onChange={({ fileList: next }) => setFileList(next)}
            >
              <div className="upload-seal"><AudioOutlined /></div>
              <p className="upload-title">拖入录音，或点击选择文件</p>
              <p className="upload-hint">单个文件不超过 200 MB</p>
            </Upload.Dragger>
            <Button type="primary" size="large" block onClick={handleUpload} disabled={!filename} loading={busy === '上传'}>
              建立会议工作区 <span aria-hidden>→</span>
            </Button>
          </div>
        </section>
      ) : (
        <section className="workspace">
          <div className="workspace-head">
            <div><p className="section-number">会议工作区</p><h2>{meeting.title}</h2><p>{meeting.filename}</p></div>
            <div className="actions">
              {meeting.status === 'uploaded' && <Button type="primary" icon={<AudioOutlined />} onClick={() => run('转写', () => transcribeMeeting(meeting.id))} loading={busy === '转写'}>开始转写</Button>}
              {meeting.status === 'transcribed' && <Button type="primary" icon={<RobotOutlined />} onClick={() => run('生成纪要', () => generateMinutes(meeting.id))} loading={busy === '生成纪要'}>生成纪要</Button>}
              {draft && <Button type="primary" icon={<EditOutlined />} onClick={handleSave} loading={busy === '保存定稿'}>保存定稿</Button>}
              {meeting.status === 'edited' && <><Button icon={<DownloadOutlined />} href={exportUrl(meeting.id, 'docx')}>导出 Word</Button><Button icon={<DownloadOutlined />} href={exportUrl(meeting.id, 'md')}>Markdown</Button></>}
            </div>
          </div>

          <div className="editor-grid">
            <article className="paper transcript-paper">
              <div className="paper-title"><span>原始材料</span><h3>语音转写</h3></div>
              {busy === '转写' ? <div className="processing"><LoadingOutlined spin /><p>正在识别录音内容…</p></div> : meeting.transcript ? <div className="transcript">{meeting.transcript}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="等待开始转写" />}
            </article>

            <article className="paper minutes-paper">
              <div className="paper-title"><span>智能整理</span><h3>会议纪要</h3></div>
              {busy === '生成纪要' ? <div className="processing"><LoadingOutlined spin /><p>Agent 正在提炼议题与行动项…</p></div> : draft ? (
                <div className="minutes-form">
                  <label>纪要标题</label><Input value={draft.title} onChange={(event) => update('title', event.target.value)} />
                  <label>会议摘要</label><TextArea autoSize={{ minRows: 3 }} value={draft.summary} onChange={(event) => update('summary', event.target.value)} />
                  <label>关键要点 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.key_points.join('\n')} onChange={(event) => update('key_points', event.target.value)} />
                  <label>会议决策 <small>每行一项</small></label><TextArea autoSize={{ minRows: 2 }} value={draft.decisions.join('\n')} onChange={(event) => update('decisions', event.target.value)} />
                  <label>行动事项 <small>每行一项</small></label><TextArea autoSize={{ minRows: 3 }} value={draft.action_items.join('\n')} onChange={(event) => update('action_items', event.target.value)} />
                </div>
              ) : <Empty image={<FileTextOutlined />} description={meeting.transcript ? '转写完成，可以生成纪要' : '纪要将在转写后生成'} />}
            </article>
          </div>
        </section>
      )}
      <footer><span>HUÍZHÌLÙ / 会智录</span><span>Powered by LangGraph</span></footer>
    </main>
  )
}

