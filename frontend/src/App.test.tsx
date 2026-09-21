// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)

vi.mock('./api', () => ({
  askMeeting: vi.fn(), chat: vi.fn().mockResolvedValue('测试回答'), createModelConfig: vi.fn(), createModelProvider: vi.fn(), deleteMeeting: vi.fn(),
  deleteModelConfig: vi.fn(), deleteModelProvider: vi.fn(), exportUrl: vi.fn(), generateMinutes: vi.fn(),
  listMeetings: vi.fn().mockResolvedValue([{ id: 'meeting-1', filename: 'weekly.mp3', title: '产品周会', created_at: '2026-09-21T00:00:00Z', status: 'transcribed', transcript: '周五发布', minutes: null }]), listModelConfigs: vi.fn().mockResolvedValue([]), listProviderModels: vi.fn().mockResolvedValue(['gpt-4o-mini', 'qwen3']),
  listModelProviders: vi.fn().mockResolvedValue([{ id: 'provider-1', name: '企业模型', protocol: 'openai_compatible', base_url: 'https://llm.example.com/v1', enabled: true, api_key_configured: true, api_key_masked: 'sk-••••test', created_at: '2026-09-21T00:00:00Z' }]), saveMinutes: vi.fn(), transcribeMeeting: vi.fn(),
  testModelProvider: vi.fn(), updateModelConfig: vi.fn(), updateModelProvider: vi.fn(), uploadRecording: vi.fn(),
}))

afterEach(cleanup)

describe('sidebar collapse control', () => {
  it('collapses and expands the sidebar', () => {
    const { container } = render(<App />)
    const layout = container.querySelector('.app-layout')

    const collapseButton = screen.getByRole('button', { name: '收起侧边栏' })
    expect(layout).not.toHaveClass('sidebar-collapsed')
    expect(collapseButton).toHaveAttribute('aria-expanded', 'true')

    fireEvent.click(collapseButton)
    expect(layout).toHaveClass('sidebar-collapsed')
    expect(screen.getByRole('button', { name: '展开侧边栏' })).toHaveAttribute('aria-expanded', 'false')
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .anticon')).toHaveLength(8)
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .nav-label')).toHaveLength(8)

    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }))
    expect(layout).not.toHaveClass('sidebar-collapsed')
  })
})

describe('model management navigation', () => {
  it('opens the model service page', async () => {
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: /模型服务/ }))

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
    fireEvent.click(screen.getByRole('button', { name: /模型服务/ }))
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
    fireEvent.click(screen.getByRole('button', { name: /会议问答/ }))

    expect(await screen.findByRole('heading', { name: '会议问答', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('普通问答')).toBeInTheDocument()
    const input = screen.getByPlaceholderText('输入问题，使用 @ 选择会议…')
    fireEvent.change(input, { target: { value: '@产品' } })
    fireEvent.click(await screen.findByRole('button', { name: /产品周会/ }))

    expect(screen.getByText('会议 RAG')).toBeInTheDocument()
    expect(screen.getByText('仅依据本次会议内容回答', { exact: false })).toBeInTheDocument()
  })
})
