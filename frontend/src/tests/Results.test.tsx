import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import React from 'react'
import Results from '../pages/Results'

vi.mock('../api/client', () => ({
  getResults: vi.fn(),
  getActiveSession: vi.fn().mockResolvedValue({ active_session_id: null }),
}))

import * as client from '../api/client'

const mockResults = {
  session_id: 'test_001',
  type: 'understanding',
  chapter: 'ch10_light',
  topic: null,
  total_marks: 10,
  score_obtained: 7,
  percentage: 70,
  status: 'scored',
  results: [
    {
      question_id: 'q1',
      question_text: 'What is reflection?',
      student_answer: 'Light bounces back',
      selected_option: null,
      score: 2,
      max_marks: 2,
      is_correct: true,
      evaluation_layer: 'keyword',
      feedback: {
        keywords_found: ['reflect'],
        points_covered: [],
        points_missed: [],
        comment: 'Good',
      },
      suggestions: null,
      model_answer: 'Reflection is the bouncing back of light',
      key_points: [],
    },
    {
      question_id: 'q2',
      question_text: 'Define refraction.',
      student_answer: 'Bending of light',
      selected_option: null,
      score: 1,
      max_marks: 2,
      is_correct: false,
      evaluation_layer: 'keyword',
      feedback: {
        keywords_found: [],
        points_covered: [],
        points_missed: ['medium change'],
        comment: 'Incomplete',
      },
      suggestions: 'Mention change of medium',
      model_answer: 'Refraction is the bending of light when it passes from one medium to another',
      key_points: ['change of medium', 'change in speed'],
    },
  ],
  xp_earned: 30,
  current_streak: 3,
  total_xp: 100,
  topic_scores: {},
  new_badges: [],
  leveled_up: false,
  current_level: 1,
}

const mockMockResults = {
  ...mockResults,
  session_id: 'mock_001',
  type: 'mock',
  chapter: 'all',
  total_marks: 80,
  score_obtained: 52,
  percentage: 65,
  chapter_breakdown: {
    ch10_light: { score: 8, max_marks: 10 },
    ch12_electricity: { score: 6, max_marks: 10 },
  },
}

function renderResults(
  state: Record<string, unknown>,
  sessionId = 'test_001',
) {
  return render(
    <MemoryRouter
      initialEntries={[
        { pathname: `/session/${sessionId}/results`, state },
      ]}
    >
      <Routes>
        <Route path="/session/:id/results" element={<Results />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Results', () => {
  beforeEach(() => {
    vi.mocked(client.getActiveSession).mockResolvedValue({ active_session_id: null })
  })

  // Test 7: renders score and percentage for a completed understanding session
  test('renders score and percentage for a completed understanding session', async () => {
    renderResults({ results: mockResults, new_badges: [], leveled_up: false })

    await waitFor(() => {
      // Score 7.0 displayed (toFixed(1))
      expect(screen.getByText('7.0')).toBeInTheDocument()
      // Percentage badge showing 70%
      expect(screen.getByText('70%')).toBeInTheDocument()
    })
  })

  // Test 8: renders FeedbackRow for each question result
  test('renders FeedbackRow for each question result', async () => {
    renderResults({ results: mockResults, new_badges: [], leveled_up: false })

    await waitFor(() => {
      expect(screen.getByText('What is reflection?')).toBeInTheDocument()
      expect(screen.getByText('Define refraction.')).toBeInTheDocument()
    })
  })

  // Test 9: shows "Badge Unlocked!" modal when new_badges is non-empty
  test('shows "Badge Unlocked!" modal when new_badges is non-empty in location.state', async () => {
    renderResults({
      results: mockResults,
      new_badges: ['first_perfect'],
      leveled_up: false,
    })

    await waitFor(() => {
      expect(screen.getByText('Badge Unlocked!')).toBeInTheDocument()
    })
  })

  // Test 10: shows "Level Up!" modal when leveled_up=true
  test('shows "Level Up!" modal when leveled_up=true in location.state', async () => {
    renderResults({
      results: mockResults,
      new_badges: [],
      leveled_up: true,
      current_level: 2,
    })

    await waitFor(() => {
      expect(screen.getByText('Level Up!')).toBeInTheDocument()
    })
  })

  // Test 11: clicking "See Results →" dismisses celebration modal
  test('clicking "See Results →" dismisses celebration modal', async () => {
    renderResults({
      results: mockResults,
      new_badges: ['first_perfect'],
      leveled_up: false,
    })

    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('Badge Unlocked!')).toBeInTheDocument()
    })

    const seeResultsBtn = screen.getByRole('button', { name: /See Results/i })
    await user.click(seeResultsBtn)

    await waitFor(() => {
      expect(screen.queryByText('Badge Unlocked!')).not.toBeInTheDocument()
    })
  })

  // Test 12: mock test results show "All 13 Science Chapters" in header
  test('mock test results show "All 13 Science Chapters" in header', async () => {
    renderResults(
      { results: mockMockResults, new_badges: [], leveled_up: false },
      'mock_001',
    )

    await waitFor(() => {
      expect(screen.getByText(/All 13 Science Chapters/i)).toBeInTheDocument()
    })
  })

  // Test 13: chapter breakdown card renders when chapter_breakdown is present
  test('chapter breakdown card renders when chapter_breakdown is present in results', async () => {
    renderResults(
      { results: mockMockResults, new_badges: [], leveled_up: false },
      'mock_001',
    )

    await waitFor(() => {
      expect(screen.getByText('Chapter-wise Breakdown')).toBeInTheDocument()
      // ch10_light label
      expect(screen.getByText('Light — Reflection & Refraction')).toBeInTheDocument()
    })
  })
})
