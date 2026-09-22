// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Modal } from 'antd'
import App from './App'
import { createDepartment, getCurrentUser, listNotifications, login, logout } from '../api'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)
vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
})))

vi.mock('../api', () => ({
  askMeeting: vi.fn(), chat: vi.fn().mockResolvedValue({ answer: '测试回答', conversation_id: 'chat-1' }),
  listChatConversations: vi.fn().mockResolvedValue([]), getChatConversation: vi.fn(), createModelConfig: vi.fn(), createModelProvider: vi.fn(), deleteMeeting: vi.fn(),
  deleteModelConfig: vi.fn(), deleteModelProvider: vi.fn(), exportUrl: vi.fn(), generateMinutes: vi.fn(),
  listMeetings: vi.fn().mockResolvedValue([{ id: 'meeting-1', filename: 'weekly.mp3', title: '产品周会', created_at: '2026-09-21T00:00:00Z', status: 'transcribed', transcript: '周五发布', minutes: null }]), listModelConfigs: vi.fn().mockResolvedValue([]), listProviderModels: vi.fn().mockResolvedValue(['gpt-4o-mini', 'qwen3']),
  listModelProviders: vi.fn().mockResolvedValue([{ id: 'provider-1', name: '企业模型', protocol: 'openai_compatible', base_url: 'https://llm.example.com/v1', enabled: true, api_key_configured: true, api_key_masked: 'sk-••••test', created_at: '2026-09-21T00:00:00Z' }]), saveMinutes: vi.fn(), transcribeMeeting: vi.fn(),
  testModelProvider: vi.fn(), updateModelConfig: vi.fn(), updateModelProvider: vi.fn(), uploadRecording: vi.fn(),
  getCurrentUser: vi.fn().mockResolvedValue({ id: 'test-user', username: 'test', display_name: '测试用户', department_id: null, is_active: true, role_ids: ['system-admin'], permissions: ['meeting:create', 'meeting:read_all', 'meeting:manage_all', 'chat:use', 'model:read', 'model:manage', 'user:read', 'user:manage', 'role:read', 'role:manage', 'department:read', 'department:manage'] }),
  getMeeting: vi.fn(), listNotifications: vi.fn().mockResolvedValue([]), login: vi.fn(), logout: vi.fn(), markNotificationRead: vi.fn(),
  listUsers: vi.fn().mockResolvedValue([{ id: 'test-user', username: 'test', display_name: '测试用户', department_id: null, is_active: true, role_ids: ['system-admin'], permissions: ['user:manage'] }]),
  listRoles: vi.fn().mockResolvedValue([{ id: 'system-admin', name: '系统管理员', description: '拥有全部权限', is_system: true, permissions: ['user:manage'], member_count: 1 }]),
  listDepartments: vi.fn().mockResolvedValue([{ id: 'dept-1', name: '研发中心', parent_id: null, sort_order: 0, member_count: 0 }]),
  listPermissions: vi.fn().mockResolvedValue([{ key: 'user:manage', label: '管理用户及其角色' }]),
  createUser: vi.fn(), updateUser: vi.fn(), deleteUser: vi.fn(), createRole: vi.fn(), updateRole: vi.fn(), deleteRole: vi.fn(), createDepartment: vi.fn(), updateDepartment: vi.fn(), deleteDepartment: vi.fn(),
}))

afterEach(() => { Modal.destroyAll(); cleanup(); document.querySelectorAll('.ant-modal-root').forEach((node) => node.remove()) })

describe('account and notifications', () => {
  it('confirms logout from the sidebar user card', async () => {
    vi.mocked(logout).mockResolvedValue(undefined)
    render(<App />)
    const userCard = await screen.findByRole('button', { name: '退出登录' })
    expect(userCard).toHaveClass('user-card')
    fireEvent.click(userCard)
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAccessibleName('确认退出登录？')
    expect(logout).not.toHaveBeenCalled()
    fireEvent.click(within(dialog).getByRole('button', { name: /取\s*消/ }))
    expect(logout).not.toHaveBeenCalled()

    fireEvent.click(userCard)
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '退出登录' }))
    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    expect(logout).toHaveBeenCalledTimes(1)
  })

  it('requires login before showing the workspace', async () => {
    vi.mocked(getCurrentUser).mockRejectedValueOnce(new Error('unauthorized'))
    vi.mocked(login).mockResolvedValueOnce({ id: 'user-1', username: 'admin', display_name: '系统管理员', department_id: null, is_active: true, role_ids: ['system-admin'], permissions: ['meeting:create', 'meeting:read_all', 'meeting:manage_all', 'chat:use', 'model:read', 'model:manage', 'user:read', 'user:manage', 'role:read', 'role:manage', 'department:read', 'department:manage'] })
    render(<App />)

    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('账号'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'password' } })
    fireEvent.click(screen.getByRole('button', { name: '登录工作台' }))

    expect(await screen.findByRole('button', { name: '收起侧边栏' })).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith('admin', 'password')
  })

  it('shows unread notifications in the bell menu', async () => {
    vi.mocked(listNotifications).mockResolvedValueOnce([{ id: 'n1', user_id: 'test-user', meeting_id: null, title: '转写完成', body: '产品周会已完成语音转写', created_at: '2026-09-21T00:00:00Z', read_at: null }])
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: '通知' }))
    expect(await screen.findByText('产品周会已完成语音转写')).toBeInTheDocument()
  })
})

describe('RBAC navigation', () => {
  it('opens user, role and department management', async () => {
    vi.mocked(createDepartment).mockResolvedValueOnce({ id: 'dept-2', name: '产品部', parent_id: null, sort_order: 0, member_count: 0 })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /权限管理/ }))
    expect(await screen.findByRole('heading', { name: '组织与权限' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /添加用户/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '角色权限' }))
    expect(await screen.findByRole('button', { name: /添加角色/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '部门管理' }))
    expect(await screen.findByRole('button', { name: /添加部门/ })).toBeInTheDocument()
    expect(await screen.findByText('研发中心 · 0 人')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /添加部门/ }))
    const dialog = await screen.findByRole('dialog', { name: '添加部门' })
    fireEvent.change(within(dialog).getByRole('textbox', { name: '部门名称' }), { target: { value: '产品部' } })
    fireEvent.click(within(dialog).getByRole('button', { name: /保\s*存/ }))
    expect(createDepartment).toHaveBeenCalledWith({ name: '产品部', parent_id: null, sort_order: 0 })
  })

  it('hides management entries for a regular member', async () => {
    vi.mocked(getCurrentUser).mockResolvedValueOnce({ id: 'member', username: 'member', display_name: '普通成员', department_id: null, is_active: true, role_ids: ['member'], permissions: ['meeting:create', 'meeting:read_own', 'meeting:manage_own', 'chat:use', 'model:read'] })
    render(<App />)
    await screen.findByRole('button', { name: '收起侧边栏' })
    expect(screen.queryByRole('button', { name: /权限管理/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /模型服务/ }))
    expect(await screen.findByRole('heading', { name: '模型服务' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '添加供应商' })).not.toBeInTheDocument()
  })
})

describe('sidebar collapse control', () => {
  it('collapses and expands the sidebar', async () => {
    const { container } = render(<App />)
    await screen.findByRole('button', { name: '收起侧边栏' })
    const layout = container.querySelector('.app-layout')

    const collapseButton = screen.getByRole('button', { name: '收起侧边栏' })
    expect(layout).not.toHaveClass('sidebar-collapsed')
    expect(collapseButton).toHaveAttribute('aria-expanded', 'true')

    fireEvent.click(collapseButton)
    expect(layout).toHaveClass('sidebar-collapsed')
    expect(screen.getByRole('button', { name: '展开侧边栏' })).toHaveAttribute('aria-expanded', 'false')
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .anticon')).toHaveLength(8)
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .nav-label')).toHaveLength(8)
    expect(container.querySelector('.sidebar-collapsed .sidebar-footer .user-card')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }))
    expect(layout).not.toHaveClass('sidebar-collapsed')
  })
})

describe('model management navigation', () => {
  it('opens the model service page', async () => {
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: /模型服务/ }))

    expect(await screen.findByRole('heading', { name: '模型服务', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('会议 RAG')).toBeInTheDocument()
    expect(screen.getByText('基于单场会议内容进行问答')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '获取模型列表' })).toHaveTextContent('模型')
    expect(screen.getByRole('button', { name: '测试供应商连接' })).toHaveTextContent('测试')
    expect(screen.getByRole('button', { name: '编辑供应商' })).toHaveTextContent('编辑')
    expect(screen.getByRole('button', { name: '删除供应商' })).toHaveTextContent('删除')
    expect(document.querySelectorAll('.provider-card .action-label')).toHaveLength(4)
  })

  it('loads provider models instead of accepting a manual model id', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /模型服务/ }))
    fireEvent.click(await screen.findByRole('button', { name: /添加模型/ }))

    expect(await screen.findByText('选择模型')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getAllByRole('combobox')[2])
    expect((await screen.findAllByText('gpt-4o-mini')).length).toBeGreaterThan(0)
    expect(screen.queryByPlaceholderText('例如：gpt-4o-mini')).not.toBeInTheDocument()
  })
})

describe('meeting chat navigation', () => {
  it('supports regular chat and selecting a meeting with @', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /会议问答/ }))

    expect(await screen.findByRole('heading', { name: '会议问答', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('普通问答')).toBeInTheDocument()
    const input = screen.getByPlaceholderText('输入问题，使用 @ 选择会议…')
    fireEvent.change(input, { target: { value: '@产品' } })
    fireEvent.click(await screen.findByRole('button', { name: /产品周会/ }))

    expect(screen.getByText('会议 RAG')).toBeInTheDocument()
    expect(screen.getByText('仅依据本次会议内容回答', { exact: false })).toBeInTheDocument()
  })

  it('opens chat with the meeting selected from records', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /会议记录/ }))
    fireEvent.click(await screen.findByRole('button', { name: '去对话产品周会' }))

    expect(await screen.findByRole('heading', { name: '会议问答', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('会议 RAG')).toBeInTheDocument()
    expect(screen.getByText('weekly.mp3 · 仅依据本次会议内容回答')).toBeInTheDocument()
  })

  it('opens a meeting with a new-meeting action and no export actions', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /会议记录/ }))
    await screen.findByText('weekly.mp3', {}, { timeout: 3000 })
    fireEvent.click(screen.getByRole('button', { name: '打开产品周会' }))

    const createButton = await screen.findByRole('button', { name: /新建会议/ })
    expect(screen.queryByText('文档导出')).not.toBeInTheDocument()
    fireEvent.click(createButton)
    expect(screen.getByRole('heading', { name: '创建会议任务', level: 2 })).toBeInTheDocument()
  })
})
