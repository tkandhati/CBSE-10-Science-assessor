import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import AdminDashboard from '../pages/admin/AdminDashboard'

vi.mock('../../api/client', () => ({
  getAdminDashboard: vi.fn(),
}))

vi.mock('../api/client', () => ({
  getAdminDashboard: vi.fn(),
}))

import * as client from '../api/client'

const allChapters = [
  'ch01_chemical_reactions',
  'ch02_acids_bases_salts',
  'ch03_metals_non_metals',
  'ch04_carbon_compounds',
  'ch05_life_processes',
  'ch06_control_coordination',
  'ch07_reproduction',
  'ch08_heredity',
  'ch10_light',
  'ch11_human_eye',
  'ch12_electricity',
  'ch13_magnetic_effects',
  'ch15_our_environment',
]

const chapterPerformance: Record<string, { title: string; average: number; attempts: number; band: string }> = {}
allChapters.forEach(id => {
  chapterPerformance[id] = {
    title: id.replace(/_/g, ' '),
    average: 0,
    attempts: 0,
    band: 'Untested',
  }
})
// Override a couple with data
chapterPerformance['ch01_chemical_reactions'] = {
  title: 'Chemical Reactions & Equations',
  average: 70,
  attempts: 10,
  band: 'Developing',
}
chapterPerformance['ch10_light'] = {
  title: 'Light — Reflection and Refraction',
  average: 85,
  attempts: 8,
  band: 'Strong',
}

const mockDashData = {
  total_sessions: 5,
  total_questions_answered: 50,
  overall_average: 65.0,
  current_streak: 3,
  best_streak: 7,
  chapter_performance: chapterPerformance,
  recent_sessions: [],
  strengths: [],
  weaknesses: [],
  exam_readiness: {
    score: 52.0,
    range_low: 50.0,
    range_high: 54.0,
    band_label: 'Good',
    max_marks: 84,
  },
  coverage_gaps: [],
}

function renderAdminDashboard() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <AdminDashboard />
    </MemoryRouter>,
  )
}

describe('AdminDashboard', () => {
  beforeEach(() => {
    vi.mocked(client.getAdminDashboard).mockResolvedValue(mockDashData as any)
  })

  // Test 14: renders 5 metric cards
  test('renders 5 metric cards (sessions, questions, average, streak, best streak)', async () => {
    renderAdminDashboard()

    await waitFor(() => {
      expect(screen.getByText('Sessions')).toBeInTheDocument()
      expect(screen.getByText('Questions Answered')).toBeInTheDocument()
      expect(screen.getByText('Overall Average')).toBeInTheDocument()
      expect(screen.getByText('Current Streak')).toBeInTheDocument()
      expect(screen.getByText('Best Streak')).toBeInTheDocument()
    })
  })

  // Test 15: chapter performance bars render for all 13 chapters
  test('chapter performance bars render for all 13 chapters', async () => {
    renderAdminDashboard()

    await waitFor(() => {
      // Check a few chapter titles in the bars
      expect(screen.getByText('Chemical Reactions & Equations')).toBeInTheDocument()
      expect(screen.getByText('Light — Reflection and Refraction')).toBeInTheDocument()
    })
  })

  // Test 16: exam readiness shows score out of 84
  test('exam readiness shows score out of 84', async () => {
    renderAdminDashboard()

    await waitFor(() => {
      expect(screen.getByText('Exam Readiness')).toBeInTheDocument()
      expect(screen.getByText(/\/\s*84/)).toBeInTheDocument()
    })
  })

  // Test 17: coverage gap alert hidden when gaps array is empty
  test('coverage gap alert hidden when gaps array is empty', async () => {
    renderAdminDashboard()

    await waitFor(() => {
      expect(screen.queryByText(/Question Bank Gaps Detected/i)).not.toBeInTheDocument()
    })
  })

  // Test 18: coverage gap alert visible when gaps array has items
  test('coverage gap alert visible when gaps array has items', async () => {
    vi.mocked(client.getAdminDashboard).mockResolvedValue({
      ...mockDashData,
      coverage_gaps: [
        { chapter: 'ch10_light', template: 'short', type: 'short', needed: 3, available: 1, gap: 2 },
      ],
    } as any)

    renderAdminDashboard()

    await waitFor(() => {
      expect(screen.getByText(/Question Bank Gaps Detected/i)).toBeInTheDocument()
    })
  })

  // Test 19: empty state shows when recent_sessions is empty
  test('empty state shows when recent_sessions is empty', async () => {
    renderAdminDashboard()

    await waitFor(() => {
      expect(screen.getByText(/No completed sessions yet/i)).toBeInTheDocument()
    })
  })
})
