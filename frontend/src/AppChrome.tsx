import {
  AppstoreOutlined, BellOutlined, CloudServerOutlined, FileTextOutlined,
  FolderOpenOutlined, LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
  MessageOutlined, SafetyCertificateOutlined, SettingOutlined, TeamOutlined,
} from '@ant-design/icons'
import { Button, Empty, Popover } from 'antd'
import type { ReactNode } from 'react'
import type { AppNotification, Meeting, User } from './types'
import { formatDate } from './RecordsPage'

export type Page = 'workspace' | 'records' | 'chat' | 'models' | 'access'

const navigation = [
  { key: 'workspace', label: '工作台', icon: AppstoreOutlined },
  { key: 'records', label: '会议记录', icon: FolderOpenOutlined },
  { key: 'chat', label: '会议问答', icon: MessageOutlined },
  { key: 'templates', label: '纪要模板', icon: FileTextOutlined },
  { key: 'team', label: '团队空间', icon: TeamOutlined },
]

interface AppChromeProps {
  user: User
  page: Page
  meeting: Meeting | null
  notifications: AppNotification[]
  sidebarCollapsed: boolean
  can: (permission: string) => boolean
  canReadMeetings: boolean
  canViewAccess: boolean
  onPageChange: (page: Page) => void
  onOpenWorkspace: (meeting?: Meeting) => void
  onOpenChat: () => void
  onLogout: () => void
  onOpenNotification: (item: AppNotification) => void
  onToggleSidebar: () => void
  children: ReactNode
}

export default function AppChrome({ user, page, meeting, notifications, sidebarCollapsed, can, canReadMeetings, canViewAccess, onPageChange, onOpenWorkspace, onOpenChat, onLogout, onOpenNotification, onToggleSidebar, children }: AppChromeProps) {
  return <div className={`app-layout${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
    <aside className="sidebar">
      <div className="brand"><span className="brand-symbol">会</span><div><strong>会智录</strong><small>MEETMIND</small></div></div>
      <nav className="main-nav" aria-label="主导航">
        <p>协作空间</p>
        {navigation.map(({ key, label, icon: Icon }) => {
          const active = page === key
          const available = key === 'workspace' ? can('meeting:create') || canReadMeetings : key === 'records' ? canReadMeetings : key === 'chat' ? can('chat:use') : false
          return <button className={active ? 'active' : ''} key={key} type="button" disabled={!available} title={available ? label : `${label}（即将开放）`} onClick={() => available && (key === 'workspace' ? onOpenWorkspace(meeting || undefined) : key === 'chat' ? onOpenChat() : onPageChange('records'))}><Icon /><span className="nav-label">{label}</span>{active && <i />}</button>
        })}
        <p>系统管理</p>
        {(can('model:read') || can('model:manage')) && <button className={page === 'models' ? 'active' : ''} type="button" onClick={() => onPageChange('models')}><CloudServerOutlined /><span className="nav-label">模型服务</span>{page === 'models' && <i />}</button>}
        {canViewAccess && <button className={page === 'access' ? 'active' : ''} type="button" onClick={() => onPageChange('access')}><SafetyCertificateOutlined /><span className="nav-label">权限管理</span>{page === 'access' && <i />}</button>}
        <button type="button"><SettingOutlined /><span className="nav-label">系统设置</span></button>
      </nav>
      <div className="sidebar-footer">
        <div className="service-state"><span />服务运行正常</div>
        <button className="user-card" type="button" aria-label="退出登录" title="退出登录" onClick={onLogout}><span className="avatar">{user.display_name.slice(0, 1)}</span><div><strong>{user.display_name}</strong><small>{user.username}</small></div><LogoutOutlined className="logout-icon" /></button>
      </div>
    </aside>

    <div className="main-column">
      <header className="topbar">
        <div className="topbar-title">
          <button className="sidebar-toggle" type="button" aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'} aria-expanded={!sidebarCollapsed} onClick={onToggleSidebar}>
            {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
          <span>智能会议工作台</span>
        </div>
        <div className="topbar-actions"><span className="environment"><i />企业专属环境</span><Popover placement="bottomRight" trigger="click" content={<div className="notification-list"><div className="notification-title"><strong>站内通知</strong>{'Notification' in window && Notification.permission === 'default' && <Button size="small" onClick={() => void Notification.requestPermission()}>开启桌面提醒</Button>}</div>{notifications.length ? notifications.map((item) => <button className={item.read_at ? 'read' : ''} type="button" key={item.id} onClick={() => onOpenNotification(item)}><strong>{item.title}</strong><span>{item.body}</span><small>{formatDate(item.created_at)}</small></button>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" />}</div>}><button aria-label="通知" type="button"><BellOutlined />{notifications.some((item) => !item.read_at) && <b>{notifications.filter((item) => !item.read_at).length}</b>}</button></Popover></div>
      </header>
      {children}
    </div>
  </div>
}
