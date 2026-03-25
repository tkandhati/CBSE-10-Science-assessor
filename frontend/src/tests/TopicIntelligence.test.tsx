import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import TopicStrengths from '../pages/admin/TopicStrengths'

vi.mock('../../api/client', () => ({
  getTopicStrengths: vi.fn(),
}))

vi.mock('../api/client', () => ({
  getTopicStrengths: vi.fn(),
}))

import * as client from '../api/client'

// Build mock data covering the 5 physics chapters the component uses in CHAPTER_ORDER
// plus extra data for untested/weak topic tests
const mockTopicsData = {
  topics: {
    'light.reflection': {
      topic_title: 'Laws of Reflection',
      chapter_id: 'light',
      chapter_title: 'Light — Reflection & Refraction',
      band: 'Strong' as const,
      score: 85,
      attempts: 5,
      last_tested: '2026-03-20T10:00:00Z',
      trend: 'up' as const,
      recommended_action: 'Maintain',
    },
    'light.refraction': {
      topic_title: 'Refraction through a Glass Slab',
      chapter_id: 'light',
      chapter_title: 'Light — Reflection & Refraction',
      band: 'Weak' as const,
      score: 35,
      attempts: 3,
      last_tested: '2026-03-18T10:00:00Z',
      trend: 'down' as const,
      recommended_action: 'Revise Now',
    },
    'human_eye.defects': {
      topic_title: 'Defects of Vision',
      chapter_id: 'human_eye',
      chapter_title: 'Human Eye & Colourful World',
      band: 'Developing' as const,
      score: 62,
      attempts: 2,
      last_tested: '2026-03-15T10:00:00Z',
      trend: 'flat' as const,
      recommended_action: 'Practice More',
    },
    'electricity.ohm': {
      topic_title: "Ohm's Law",
      chapter_id: 'electricity',
      chapter_title: 'Electricity',
      band: 'Untested' as const,
      score: 0,
      attempts: 0,
      last_tested: null,
      trend: 'flat' as const,
      recommended_action: 'Start Practising',
    },
    'magnetic_effects.flemings': {
      topic_title: "Fleming's Left Hand Rule",
      chapter_id: 'magnetic_effects',
      chapter_title: 'Magnetic Effects of Current',
      band: 'Untested' as const,
      score: 0,
      attempts: 0,
      last_tested: null,
      trend: 'flat' as const,
      recommended_action: 'Start Practising',
    },
    'sources_of_energy.solar': {
      topic_title: 'Solar Energy',
      chapter_id: 'sources_of_energy',
      chapter_title: 'Sources of Energy',
      band: 'Critical' as const,
      score: 20,
      attempts: 1,
      last_tested: '2026-03-10T10:00:00Z',
      trend: 'down' as const,
      recommended_action: 'Revise Now',
    },
  },
  weak_topics: [
    {
      topic_key: 'light.refraction',
      topic_title: 'Refraction through a Glass Slab',
      chapter_id: 'light',
      chapter_title: 'Light — Reflection & Refraction',
      score: 35,
      attempts: 3,
      last_tested: '2026-03-18T10:00:00Z',
    },
    {
      topic_key: 'sources_of_energy.solar',
      topic_title: 'Solar Energy',
      chapter_id: 'sources_of_energy',
      chapter_title: 'Sources of Energy',
      score: 20,
      attempts: 1,
      last_tested: '2026-03-10T10:00:00Z',
    },
  ],
  untested_topics: [
    {
      topic_key: 'electricity.ohm',
      topic_title: "Ohm's Law",
      chapter_id: 'electricity',
      chapter_title: 'Electricity',
      attempts: 0,
    },
    {
      topic_key: 'magnetic_effects.flemings',
      topic_title: "Fleming's Left Hand Rule",
      chapter_id: 'magnetic_effects',
      chapter_title: 'Magnetic Effects of Current',
      attempts: 0,
    },
  ],
}

const mockTopicsNoWeak = {
  ...mockTopicsData,
  weak_topics: [],
}

function renderTopicStrengths() {
  return render(
    <MemoryRouter initialEntries={['/admin/strengths']}>
      <TopicStrengths />
    </MemoryRouter>,
  )
}

describe('TopicStrengths (Topic Intelligence)', () => {
  beforeEach(() => {
    vi.mocked(client.getTopicStrengths).mockResolvedValue(mockTopicsData as any)
  })

  // Test 20: renders page title "Topic Intelligence"
  test('renders page title "Topic Intelligence"', async () => {
    renderTopicStrengths()

    await waitFor(() => {
      expect(screen.getByText('Topic Intelligence')).toBeInTheDocument()
    })
  })

  // Test 21: weak topics panel shows when weaknesses exist
  test('weak topics panel shows when weaknesses exist', async () => {
    renderTopicStrengths()

    await waitFor(() => {
      expect(screen.getByText(/Top 5 Weakest Topics/i)).toBeInTheDocument()
      // The topic title appears in multiple places (summary panel + accordion), use getAllByText
      const titleMatches = screen.getAllByText('Refraction through a Glass Slab')
      expect(titleMatches.length).toBeGreaterThan(0)
    })
  })

  // Test 22: "No weak topics" message shown when weaknesses empty
  test('"No weak topics" message not present when weaknesses empty — panel hidden', async () => {
    vi.mocked(client.getTopicStrengths).mockResolvedValue(mockTopicsNoWeak as any)
    renderTopicStrengths()

    await waitFor(() => {
      expect(screen.queryByText(/Top 5 Weakest Topics/i)).not.toBeInTheDocument()
    })
  })

  // Test 23: untested topics panel shows grey pills
  test('untested topics panel shows untested topic pills', async () => {
    renderTopicStrengths()

    await waitFor(() => {
      expect(screen.getByText(/Untested Topics/i)).toBeInTheDocument()
      expect(screen.getByText("Ohm's Law")).toBeInTheDocument()
    })
  })

  // Test 24: all relevant chapters appear in chapter accordion
  test('chapters from data appear in chapter accordion', async () => {
    renderTopicStrengths()

    await waitFor(() => {
      // "light" chapter title appears (may appear in weak topics panel + accordion), use getAllByText
      const lightMatches = screen.getAllByText('Light — Reflection & Refraction')
      expect(lightMatches.length).toBeGreaterThan(0)
      // Human Eye chapter
      expect(screen.getByText('Human Eye & Colourful World')).toBeInTheDocument()
    })
  })

  // Test 25: trend "up" shows upward arrow ↑
  test('trend "up" shows upward arrow symbol', async () => {
    renderTopicStrengths()

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Topic Intelligence')).toBeInTheDocument()
    })

    // light chapter has a weak topic so accordion is auto-opened
    // The 'up' trend for Laws of Reflection should show ↑
    await waitFor(() => {
      const arrows = screen.getAllByText('↑')
      expect(arrows.length).toBeGreaterThan(0)
    })
  })
})
