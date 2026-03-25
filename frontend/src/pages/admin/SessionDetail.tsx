import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAdminSessionDetail, overrideAnswerScore } from '../../api/client'
import type { AdminSessionDetail, AdminAnswerDetail } from '../../types'

const LAYER_COLOR: Record<string, string> = {
  deterministic: 'bg-blue-100 text-blue-700',
  keyword:       'bg-amber-100 text-amber-700',
  ai:            'bg-purple-100 text-purple-700',
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

function formatType(type: string) {
  const map: Record<string, string> = {
    understanding: 'Understanding', chapter_short: 'Short Test',
    chapter_regular: 'Regular Test', mock: 'Mock Test',
  }
  return map[type] ?? type
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? Math.round(score / max * 100) : 0
  const color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700 w-12 text-right">{score}/{max}</span>
    </div>
  )
}

function OverridePanel({
  answer,
  sessionId,
  onOverridden,
}: {
  answer: AdminAnswerDetail
  sessionId: string
  onOverridden: (answerId: string, newScore: number) => void
}) {
  const [open, setOpen]   = useState(false)
  const [score, setScore] = useState(String(answer.override_score ?? answer.score))
  const [note, setNote]   = useState(answer.override_note ?? '')
  const [saving, setSaving] = useState(false)
  const [err, setErr]     = useState('')

  async function handleSave() {
    const s = parseFloat(score)
    if (isNaN(s) || s < 0 || s > answer.max_marks) {
      setErr(`Score must be 0–${answer.max_marks}`)
      return
    }
    setSaving(true)
    setErr('')
    try {
      await overrideAnswerScore(sessionId, answer.id, s, note)
      onOverridden(answer.id, s)
      setOpen(false)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to save override')
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-purple-600 underline hover:text-purple-800"
      >
        Override score
      </button>
    )
  }

  return (
    <div className="mt-2 p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
      <p className="font-medium text-purple-800 mb-2">Override Score (max {answer.max_marks})</p>
      <div className="flex gap-2 mb-2">
        <input
          type="number" min={0} max={answer.max_marks} step={0.5}
          className="w-20 border rounded px-2 py-1 text-sm"
          value={score} onChange={e => setScore(e.target.value)}
        />
        <input
          type="text" placeholder="Note (optional)"
          className="flex-1 border rounded px-2 py-1 text-sm"
          value={note} onChange={e => setNote(e.target.value)}
        />
      </div>
      {err && <p className="text-red-600 text-xs mb-2">{err}</p>}
      <div className="flex gap-2">
        <button
          onClick={handleSave} disabled={saving}
          className="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-gray-500 underline">Cancel</button>
      </div>
    </div>
  )
}

function AnswerCard({
  answer,
  sessionId,
  sessionType,
  onOverridden,
}: {
  answer: AdminAnswerDetail
  sessionId: string
  sessionType: string
  onOverridden: (answerId: string, newScore: number) => void
}) {
  const isPaperTest = sessionType !== 'understanding'
  const isAIScored  = answer.evaluation_layer === 'ai'
  const pct = answer.max_marks > 0 ? Math.round(answer.score / answer.max_marks * 100) : 0
  const scoreColor = pct >= 80 ? 'text-green-700 bg-green-50 border-green-200'
                   : pct >= 50 ? 'text-amber-700 bg-amber-50 border-amber-200'
                   :             'text-red-700 bg-red-50 border-red-200'

  return (
    <div className="border rounded-xl p-4 mb-3 bg-white">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <p className="text-sm text-gray-800 flex-1 font-medium">{answer.question_text}</p>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${scoreColor}`}>
            {answer.score}/{answer.max_marks}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${LAYER_COLOR[answer.evaluation_layer] ?? 'bg-gray-100 text-gray-600'}`}>
            {answer.evaluation_layer}
          </span>
        </div>
      </div>

      <ScoreBar score={answer.score} max={answer.max_marks} />

      {/* Student answer */}
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-gray-400 mb-1 font-medium">Student Answer</p>
          <div className="bg-gray-50 rounded-lg p-2.5 text-gray-700 text-sm min-h-[40px]">
            {(isPaperTest ? (answer.ocr_text || answer.answer_text) : answer.answer_text) || <span className="text-gray-300 italic">No answer</span>}
          </div>
        </div>
        {answer.model_answer && (
          <div>
            <p className="text-xs text-gray-400 mb-1 font-medium">Model Answer</p>
            <div className="bg-blue-50 rounded-lg p-2.5 text-blue-800 text-sm min-h-[40px]">
              {answer.model_answer}
            </div>
          </div>
        )}
      </div>

      {/* Feedback */}
      {answer.feedback && (
        <div className="mt-3 text-sm">
          {answer.feedback.points_covered?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1">
              {answer.feedback.points_covered.map((p, i) => (
                <span key={i} className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full border border-green-100">✓ {p}</span>
              ))}
            </div>
          )}
          {answer.feedback.points_missed?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1">
              {answer.feedback.points_missed.map((p, i) => (
                <span key={i} className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full border border-red-100">✗ {p}</span>
              ))}
            </div>
          )}
          {answer.feedback.comment && (
            <p className="text-gray-500 text-xs mt-1 italic">{answer.feedback.comment}</p>
          )}
        </div>
      )}

      {/* Suggestions */}
      {answer.suggestions && (Array.isArray(answer.suggestions) ? answer.suggestions.join(' ') : answer.suggestions) && (
        <p className="mt-2 text-xs text-blue-700 bg-blue-50 px-3 py-2 rounded-lg">
          {Array.isArray(answer.suggestions) ? answer.suggestions.join(' ') : answer.suggestions}
        </p>
      )}

      {/* Override */}
      {isAIScored && (
        <div className="mt-3 border-t pt-2">
          {answer.override_score !== null && (
            <p className="text-xs text-purple-600 mb-1">
              Overridden to {answer.override_score}/{answer.max_marks}
              {answer.override_note ? ` — "${answer.override_note}"` : ''}
            </p>
          )}
          <OverridePanel answer={answer} sessionId={sessionId} onOverridden={onOverridden} />
        </div>
      )}
    </div>
  )
}

export default function SessionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [data, setData]     = useState<AdminSessionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    if (!id) return
    getAdminSessionDetail(id)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  function handleOverridden(answerId: string, newScore: number) {
    if (!data) return
    setData(prev => {
      if (!prev) return prev
      const answers = prev.answers.map(a =>
        a.id === answerId ? { ...a, score: newScore, override_score: newScore } : a
      )
      return { ...prev, answers }
    })
  }

  if (loading) return <div className="text-gray-400 text-sm mt-8 text-center">Loading session…</div>
  if (error)   return <div className="text-red-500 text-sm mt-8 text-center">{error}</div>
  if (!data)   return null

  const { session, answers, marks_lost_by_type, marks_lost_by_reason } = data
  const totalLost = Object.values(marks_lost_by_type).reduce((a, b) => a + b, 0)

  return (
    <div className="max-w-4xl mx-auto pb-16">
      <button onClick={() => navigate(-1)} className="text-sm text-blue-600 mb-4 hover:underline">← Back</button>

      {/* Session header */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-800 mb-1">
              {formatType(session.type)}
              {session.chapter !== 'all' && <span className="text-gray-400 font-normal ml-2">— {session.chapter}</span>}
            </h1>
            <p className="text-sm text-gray-400">{formatDate(session.started_at)}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-gray-800">{session.score_obtained}/{session.total_marks}</p>
            <p className="text-sm text-gray-400">{session.percentage}%</p>
          </div>
        </div>
        {session.overall_guidance && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-800 border border-blue-100">
            {session.overall_guidance}
          </div>
        )}
      </div>

      {/* Marks lost analysis */}
      {totalLost > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-white rounded-xl border p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Marks Lost by Question Type</h2>
            {Object.entries(marks_lost_by_type).map(([type, lost]) => (
              <div key={type} className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 capitalize">{type.replace(/_/g, ' ')}</span>
                <span className="font-semibold text-red-600">−{lost}</span>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-xl border p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Marks Lost by Reason</h2>
            {Object.entries(marks_lost_by_reason).map(([reason, count]) => (
              <div key={reason} className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 capitalize">{reason}</span>
                <span className="font-semibold text-orange-600">{count}×</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-question breakdown */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">Question Breakdown ({answers.length} questions)</h2>
      {answers.map(a => (
        <AnswerCard
          key={a.id}
          answer={a}
          sessionId={id!}
          sessionType={session.type}
          onOverridden={handleOverridden}
        />
      ))}
    </div>
  )
}
