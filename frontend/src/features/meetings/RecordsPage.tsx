import { AudioOutlined, CheckCircleFilled, DeleteOutlined, FolderOpenOutlined, LoadingOutlined, MessageOutlined, PlusOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Select, Spin, Table, Tag } from 'antd'
import type { Meeting } from '../../shared/types'

export const statusMeta = {
  uploaded: { label: '待转写', color: 'default' },
  queued: { label: '排队中', color: 'processing' },
  transcribing: { label: '转写中', color: 'processing' },
  transcription_failed: { label: '转写失败', color: 'error' },
  transcribed: { label: '待生成', color: 'processing' },
  generated: { label: '待定稿', color: 'warning' },
  edited: { label: '已完成', color: 'success' },
} as const

export function formatDate(value?: string) {
  if (!value) return '刚刚创建'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
}

interface RecordsPageProps {
  records: Meeting[]
  visibleRecords: Meeting[]
  loading: boolean
  query: string
  statusFilter: string
  onQueryChange: (value: string) => void
  onStatusChange: (value: string) => void
  onRefresh: () => void
  onOpen: (meeting: Meeting) => void
  onChat: (meeting: Meeting) => void
  onDelete: (meeting: Meeting) => void
  onCreate: () => void
  canCreate: boolean
  canChat: boolean
  canManage: boolean
}

export default function RecordsPage({
  records, visibleRecords, loading, query, statusFilter, onQueryChange,
  onStatusChange, onRefresh, onOpen, onChat, onDelete, onCreate, canCreate, canChat, canManage,
}: RecordsPageProps) {
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
      title: '操作', key: 'actions', width: 130, align: 'right' as const,
      render: (_: unknown, item: Meeting) => <div className="record-actions"><Button size="small" icon={<FolderOpenOutlined />} aria-label={`打开${item.title}`} title="打开会议" onClick={() => onOpen(item)} />{canChat && <Button size="small" icon={<MessageOutlined />} aria-label={`去对话${item.title}`} title="去对话" onClick={() => onChat(item)} />}{canManage && <Button size="small" danger icon={<DeleteOutlined />} aria-label={`删除${item.title}`} title="删除会议" onClick={() => onDelete(item)} />}</div>,
    },
  ]

  return <>
    <div className="page-heading records-heading">
      <div><p className="breadcrumb">工作台&nbsp;&nbsp;/&nbsp;&nbsp;会议记录</p><h1>会议记录</h1><p>统一管理会议录音、转写内容与会议纪要</p></div>
      {canCreate && <Button type="primary" size="large" icon={<PlusOutlined />} onClick={onCreate}>新建会议</Button>}
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
        <Table<Meeting> rowKey="id" columns={columns} dataSource={visibleRecords} pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 条记录` }} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={query || statusFilter !== 'all' ? '没有符合条件的会议记录' : '暂无会议记录'}>{canCreate && <Button type="primary" onClick={onCreate}>创建第一场会议</Button>}</Empty> }} />
      </Spin>
    </section>
  </>
}
