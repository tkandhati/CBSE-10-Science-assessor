import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock fetch globally
global.fetch = vi.fn()

// Mock window.URL.createObjectURL
if (typeof window !== 'undefined') {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
}

// Helper to reset mocks
export function mockFetch(responses: Record<string, unknown>) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
    const path = (url as string).replace('/api', '')
    const body = responses[path] ?? responses['*'] ?? {}
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
    })
  })
}

// Helper: render with MemoryRouter
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'

export function renderWithRouter(
  ui: React.ReactElement,
  { route = '/' }: { route?: string } = {},
) {
  return render(
    React.createElement(MemoryRouter, { initialEntries: [route] }, ui),
  )
}
