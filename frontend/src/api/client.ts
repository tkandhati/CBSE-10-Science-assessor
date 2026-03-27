import type {
  AnswerSubmission, SessionResponse, SessionResults, UploadOCRResult,
  AdminDashboardData, AdminSessionDetail, TopicStrengthsData, GuidanceData, ChapterInfo,
} from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Student session API ────────────────────────────────────────────────────────

export function createSession(type: string, chapter: string, topic?: string): Promise<SessionResponse> {
  return request('/session/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, chapter, topic: topic || null }),
  })
}

export function getActiveSession() {
  return request<{ active_session_id: string | null; type?: string; chapter?: string; status?: string }>('/session/active')
}

export function getSessionQuestions(sessionId: string) {
  return request<SessionResponse>(`/session/${sessionId}/questions`)
}

export function submitSession(sessionId: string, answers: AnswerSubmission[]): Promise<SessionResults> {
  return request(`/session/${sessionId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })
}

export function getResults(sessionId: string): Promise<SessionResults> {
  return request(`/session/${sessionId}/results`)
}

export function markDoneWriting(sessionId: string): Promise<{ session_id: string; status: string }> {
  return request(`/session/${sessionId}/mark-done-writing`, { method: 'PUT' })
}

export function uploadPDF(sessionId: string, file: File): Promise<UploadOCRResult> {
  const form = new FormData()
  form.append('file', file)
  return request(`/session/${sessionId}/upload-pdf`, { method: 'POST', body: form })
}

export function confirmOCR(
  sessionId: string,
  confirmations: { question_id: string; answer_text: string }[],
): Promise<{ status: string }> {
  return request(`/session/${sessionId}/confirm-ocr`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmations }),
  })
}

export function submitChapterTest(sessionId: string): Promise<SessionResults & { overall_guidance: string }> {
  return request(`/session/${sessionId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
}

export function getSyllabus() {
  return request<{ chapters: ChapterInfo[] }>('/syllabus').catch(() =>
    fetch('/data/config/syllabus.json').then(r => r.json())
  )
}

// ── Countdown API ─────────────────────────────────────────────────────────────

export interface CountdownData {
  days_remaining: number
  exam_date: string
  projected_score: number
  projected_max: number
  pace_label: 'Getting Started' | 'Behind' | 'On Track' | 'Ahead'
  weekly_target: { understanding: number; chapter_test: number }
  weekly_done:   { understanding: number; chapter_test: number }
  advice: string
}

export function getCountdown(): Promise<CountdownData> {
  return request('/student/countdown')
}

// ── Daily Spark API ───────────────────────────────────────────────────────────

export function sparkTodayStatus(): Promise<{ completed_today: boolean; session_id: string | null }> {
  return request('/spark/today')
}

export function startSpark(): Promise<{ session_id: string; chapter: string; topic: string; questions: any[] }> {
  return request('/spark/start', { method: 'POST' })
}

export function completeSpark(
  sessionId: string,
  correctCount: number,
): Promise<{ status: string; xp_gained: number; current_streak: number; total_xp: number }> {
  return request(`/spark/${sessionId}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correct_count: correctCount }),
  })
}

// ── Admin API ─────────────────────────────────────────────────────────────────

export function getAdminDashboard(): Promise<AdminDashboardData> {
  return request('/admin/dashboard')
}

export function getTopicStrengths(): Promise<TopicStrengthsData> {
  return request('/admin/strengths')
}

export function getAdminSessions(params?: { page?: number; limit?: number; chapter?: string; type?: string }) {
  const qs = new URLSearchParams()
  if (params?.page)    qs.set('page',    String(params.page))
  if (params?.limit)   qs.set('limit',   String(params.limit))
  if (params?.chapter) qs.set('chapter', params.chapter)
  if (params?.type)    qs.set('type',    params.type)
  const query = qs.toString() ? `?${qs}` : ''
  return request<{ sessions: import('../types').AdminSession[]; total: number; page: number; limit: number }>(
    `/admin/sessions${query}`
  )
}

export function getAdminSessionDetail(sessionId: string): Promise<AdminSessionDetail> {
  return request(`/admin/session/${sessionId}`)
}

export function overrideAnswerScore(
  sessionId: string,
  answerId: string,
  score: number,
  note: string,
): Promise<{ score: number; new_total: number; new_percentage: number }> {
  return request(`/admin/session/${sessionId}/answer/${answerId}/override`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ score, note }),
  })
}

export function getCoverage() {
  return request<{ gaps: import('../types').CoverageGap[]; chapter_counts: Record<string, number> }>('/admin/coverage')
}

export function getStudyGuidance(refresh = false): Promise<GuidanceData> {
  return request(`/admin/guidance${refresh ? '?refresh=true' : ''}`)
}

// ── Student/Gamification API ───────────────────────────────────────────────

export function getStudentProfile(): Promise<import('../types').StudentProfile> {
  return request('/student/profile')
}

export function getStudentBadges(): Promise<{ badges: import('../types').BadgeInfo[] }> {
  return request('/student/badges')
}

// ── Question Bank API ─────────────────────────────────────────────────────

export function getQBankStats(): Promise<import('../types').QBankStats> {
  return request('/qbank/stats')
}

export function getReviewQueue(params?: { chapter?: string; topic?: string; type?: string; page?: number; limit?: number }) {
  const qs = new URLSearchParams()
  if (params?.chapter) qs.set('chapter', params.chapter)
  if (params?.topic)   qs.set('topic', params.topic)
  if (params?.type)    qs.set('type', params.type)
  if (params?.page)    qs.set('page',  String(params.page))
  if (params?.limit)   qs.set('limit', String(params.limit))
  const query = qs.toString() ? `?${qs}` : ''
  return request<{ questions: import('../types').ReviewQueueQuestion[]; total: number; page: number; limit: number }>(
    `/qbank/review-queue${query}`
  )
}

export function approveQuestion(questionId: string): Promise<{ question_id: string; status: string }> {
  return request(`/qbank/${questionId}/approve`, { method: 'PUT' })
}

export function rejectQuestion(questionId: string): Promise<{ question_id: string; status: string }> {
  return request(`/qbank/${questionId}/reject`, { method: 'PUT' })
}

export function editQuestion(questionId: string, body: {
  text?: string; topic?: string; type?: string; difficulty?: number; marks?: number
  tags?: string; rubric_keywords?: string[]; rubric_key_points?: string[]; rubric_expected_answer?: string
}): Promise<{ question_id: string; status: string }> {
  return request(`/qbank/${questionId}/edit`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getLiveBank(params?: { chapter?: string; topic?: string; type?: string; difficulty?: number; search?: string; page?: number; limit?: number }) {
  const qs = new URLSearchParams()
  if (params?.chapter)    qs.set('chapter',    params.chapter)
  if (params?.topic)      qs.set('topic',      params.topic)
  if (params?.type)       qs.set('type',       params.type)
  if (params?.difficulty) qs.set('difficulty', String(params.difficulty))
  if (params?.search)     qs.set('search',     params.search)
  if (params?.page)       qs.set('page',       String(params.page))
  if (params?.limit)      qs.set('limit',      String(params.limit))
  const query = qs.toString() ? `?${qs}` : ''
  return request<{ questions: import('../types').LiveQuestion[]; total: number; page: number; limit: number }>(
    `/qbank/live${query}`
  )
}

export function scanPDF(file: File): Promise<{ status: string; queued: number }> {
  const form = new FormData()
  form.append('file', file)
  return request('/qbank/scan-pdf', { method: 'POST', body: form })
}

export function retagQuestions(chapter?: string, topic?: string): Promise<{ status: string; retagged: number }> {
  const qs = new URLSearchParams()
  if (chapter) qs.set('chapter', chapter)
  if (topic)   qs.set('topic', topic)
  return request(`/qbank/retag?${qs}`, { method: 'POST' })
}
