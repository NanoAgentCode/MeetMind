// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./api', () => ({
  askMeeting: vi.fn(), createModelConfig: vi.fn(), createModelProvider: vi.fn(), deleteMeeting: vi.fn(),
  deleteModelConfig: vi.fn(), deleteModelProvider: vi.fn(), exportUrl: vi.fn(), generateMinutes: vi.fn(),
  listMeetings: vi.fn().mockResolvedValue([]), listModelConfigs: vi.fn().mockResolvedValue([]),
  listModelProviders: vi.fn().mockResolvedValue([]), saveMinutes: vi.fn(), transcribeMeeting: vi.fn(),
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
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .anticon')).toHaveLength(7)
    expect(container.querySelectorAll('.sidebar-collapsed .main-nav .nav-label')).toHaveLength(7)

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
  })
})
