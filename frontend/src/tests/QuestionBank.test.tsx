import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import QuestionBank from '../pages/admin/QuestionBank'

vi.mock('../../api/client', () => ({
  getQBankStats: vi.fn(),
  getReviewQueue: vi.fn(),
  getLiveBank: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
  editQuestion: vi.fn(),
  scanPDF: vi.fn(),
  retagQuestions: vi.fn(),
  getCoverage: vi.fn(),
}))

vi.mock('../api/client', () => ({
  getQBankStats: vi.fn(),
  getReviewQueue: vi.fn(),
  getLiveBank: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
  editQuestion: vi.fn(),
  scanPDF: vi.fn(),
  retagQuestions: vi.fn(),
  getCoverage: vi.fn(),
}))

import * as client from '../api/client'

const mockStats = {
  total: 120,
  approved: 95,
  pending_review: 8,
  by_chapter: {},
  by_type: {},
  by_difficulty: {},
}

const mockReviewQuestions = [
  {
    id: 'q_001',
    chapter: 'light',
    topic: 'reflection',
    type: 'short',
    difficulty: 2,
    marks: 2,
    text: 'State the laws of reflection.',
    options: null,
    rubric: null,
    source: 'manual',
    board_years: '',
    tags: '',
    added_at: '2026-03-01T10:00:00Z',
    status: 'pending_review',
  },
  {
    id: 'q_002',
    chapter: 'electricity',
    topic: 'ohm',
    type: 'mcq',
    difficulty: 1,
    marks: 1,
    text: "What does Ohm's law state?",
    options: [
      { text: 'V = IR', is_correct: true },
      { text: 'V = I/R', is_correct: false },
    ],
    rubric: null,
    source: 'pdf_ocr',
    board_years: '2023',
    tags: '',
    added_at: '2026-03-02T10:00:00Z',
    status: 'pending_review',
  },
]

function renderQuestionBank() {
  return render(
    <MemoryRouter initialEntries={['/admin/questions']}>
      <QuestionBank />
    </MemoryRouter>,
  )
}

describe('QuestionBank', () => {
  beforeEach(() => {
    vi.mocked(client.getQBankStats).mockResolvedValue(mockStats as any)
    vi.mocked(client.getCoverage).mockResolvedValue({ gaps: [], chapter_counts: {} } as any)
    vi.mocked(client.getReviewQueue).mockResolvedValue({
      questions: mockReviewQuestions,
      total: 2,
      page: 1,
      limit: 30,
    } as any)
    vi.mocked(client.getLiveBank).mockResolvedValue({
      questions: [],
      total: 0,
      page: 1,
      limit: 20,
    } as any)
    vi.mocked(client.approveQuestion).mockResolvedValue({
      question_id: 'q_001',
      status: 'approved',
    } as any)
    vi.mocked(client.rejectQuestion).mockResolvedValue({
      question_id: 'q_001',
      status: 'rejected',
    } as any)
  })

  // Test 26: renders 4 tab buttons
  test('renders 4 tab buttons (Review Queue, Live Bank, Upload PDF, Retag)', async () => {
    renderQuestionBank()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Review Queue/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Live Bank/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Upload PDF/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Retag/i })).toBeInTheDocument()
    })
  })

  // Test 27: stats panel shows total, approved, pending counts
  test('stats panel shows total, approved, pending review counts', async () => {
    renderQuestionBank()

    await waitFor(() => {
      expect(screen.getByText('120')).toBeInTheDocument()   // total
      expect(screen.getByText('95')).toBeInTheDocument()    // approved
      expect(screen.getByText('8')).toBeInTheDocument()     // pending review
      expect(screen.getByText('Total Questions')).toBeInTheDocument()
      expect(screen.getByText('Approved')).toBeInTheDocument()
      expect(screen.getByText('Pending Review')).toBeInTheDocument()
    })
  })

  // Test 28: review queue tab shows question cards with Approve and Reject buttons
  test('review queue tab shows question cards with Approve and Reject buttons', async () => {
    renderQuestionBank()

    await waitFor(() => {
      expect(screen.getByText('State the laws of reflection.')).toBeInTheDocument()
      expect(screen.getByText("What does Ohm's law state?")).toBeInTheDocument()
    })

    // Both questions should have Approve buttons
    const approveButtons = screen.getAllByRole('button', { name: /Approve/i })
    expect(approveButtons.length).toBe(2)

    // Both questions should have Reject buttons
    const rejectButtons = screen.getAllByRole('button', { name: /Reject/i })
    expect(rejectButtons.length).toBe(2)
  })

  // Test 29: clicking Approve calls approveQuestion API and removes from list
  test('clicking Approve calls approveQuestion and removes question from list', async () => {
    renderQuestionBank()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByText('State the laws of reflection.')).toBeInTheDocument()
    })

    const approveButtons = screen.getAllByRole('button', { name: /Approve/i })
    await user.click(approveButtons[0])

    await waitFor(() => {
      expect(vi.mocked(client.approveQuestion)).toHaveBeenCalledWith('q_001')
      expect(screen.queryByText('State the laws of reflection.')).not.toBeInTheDocument()
    })
  })

  // Test 30: upload PDF tab renders file input
  test('upload PDF tab renders file input', async () => {
    renderQuestionBank()
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Upload PDF/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Upload PDF/i }))

    await waitFor(() => {
      // File input should exist (hidden but in DOM)
      const fileInput = document.querySelector('input[type="file"]')
      expect(fileInput).toBeInTheDocument()
      expect(fileInput).toHaveAttribute('accept', '.pdf')
    })
  })
})
