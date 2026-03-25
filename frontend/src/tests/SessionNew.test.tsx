import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import StartSession from '../pages/StartSession'

// Mock the api/client module
vi.mock('../api/client', () => ({
  createSession: vi.fn(),
  getSyllabus: vi.fn().mockResolvedValue({ chapters: [] }),
  getActiveSession: vi.fn().mockResolvedValue({ active_session_id: null }),
}))

import * as client from '../api/client'

function renderStartSession() {
  return render(
    <MemoryRouter initialEntries={['/session/new']}>
      <StartSession />
    </MemoryRouter>,
  )
}

describe('StartSession', () => {
  beforeEach(() => {
    vi.mocked(client.getSyllabus).mockResolvedValue({ chapters: [] })
    vi.mocked(client.getActiveSession).mockResolvedValue({ active_session_id: null })
  })

  // Test 1: renders all 4 mode options
  test('renders all 4 mode options', async () => {
    renderStartSession()
    await waitFor(() => {
      expect(screen.getByText('Understanding Session')).toBeInTheDocument()
      expect(screen.getByText('Short Chapter Test')).toBeInTheDocument()
      expect(screen.getByText('Regular Chapter Test')).toBeInTheDocument()
      expect(screen.getByText('Full Mock Test')).toBeInTheDocument()
    })
  })

  // Test 2: chapter dropdown renders with 13 chapters listed
  test('chapter dropdown renders with 13 chapters listed', async () => {
    renderStartSession()
    // Understanding mode is default — chapter dropdown is shown
    await waitFor(() => {
      const select = screen.getByRole('combobox')
      const options = select.querySelectorAll('option')
      // 13 chapter options + 1 placeholder "-- Select a chapter --"
      expect(options.length).toBe(14)
    })
  })

  // Test 3: start button is disabled when chapter is not selected for chapter_short mode
  test('start button is disabled when chapter is not selected for chapter_short mode', async () => {
    renderStartSession()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Short Chapter Test')).toBeInTheDocument()
    })

    // Click Short Chapter Test mode
    await user.click(screen.getByText('Short Chapter Test'))

    // Button should be disabled (no chapter selected)
    const startBtn = screen.getByRole('button', { name: /Start Session/i })
    expect(startBtn).toBeDisabled()
  })

  // Test 4: mock mode shows info card about 13 Science chapters and 80 marks
  test('mock mode shows info card about 13 Science chapters and 80 marks', async () => {
    renderStartSession()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Full Mock Test')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Full Mock Test'))

    await waitFor(() => {
      expect(
        screen.getByText(/Full mock covers all 13 Science chapters/i),
      ).toBeInTheDocument()
    })
  })

  // Test 5: clicking Start for mock (not confirmed) changes button text to confirmation step
  test('clicking Start for mock shows "Review & Start Mock →" then "Start Mock Test" after click', async () => {
    renderStartSession()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Full Mock Test')).toBeInTheDocument()
    })

    // Select mock mode
    await user.click(screen.getByText('Full Mock Test'))

    // First click — shows the review step button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Review & Start Mock/i })).toBeInTheDocument()
    })

    // Click "Review & Start Mock →" to trigger confirmation
    await user.click(screen.getByRole('button', { name: /Review & Start Mock/i }))

    // After confirmation, button text should change to "Start Mock Test"
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start Mock Test/i })).toBeInTheDocument()
    })
  })

  // Test 6: resume warning banner appears when active test exists
  test('resume warning banner appears when active test exists', async () => {
    vi.mocked(client.getActiveSession).mockResolvedValue({
      active_session_id: 'test123',
      status: 'in_progress',
      type: 'chapter_short',
    })

    renderStartSession()

    await waitFor(() => {
      expect(screen.getByText(/Chapter test in progress/i)).toBeInTheDocument()
      expect(screen.getByText(/Resume it/i)).toBeInTheDocument()
    })
  })
})
