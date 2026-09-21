// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

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

    fireEvent.click(screen.getByRole('button', { name: '展开侧边栏' }))
    expect(layout).not.toHaveClass('sidebar-collapsed')
  })
})
