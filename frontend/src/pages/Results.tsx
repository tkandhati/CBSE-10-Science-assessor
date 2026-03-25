import { useEffect, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { getResults, getActiveSession } from '../api/client'
import type { SessionResults, QuestionResult, SectionBreakdown } from '../types'

type ExtendedResults = SessionResults

interface ExtendedQuestionResult extends QuestionResult {
  question_type?: string
  difficulty?: number
}

const CHAPTER_LABELS: Record<string, string> = {
  ch01_chemical_reactions:   'Chemical Reactions & Equations',
  ch02_acids_bases_salts:    'Acids, Bases and Salts',
  ch03_metals_non_metals:    'Metals and Non-Metals',
  ch04_carbon_compounds:     'Carbon and its Compounds',
  ch05_life_processes:       'Life Processes',
  ch06_control_coordination: 'Control and Coordination',
  ch07_reproduction:         'How do Organisms Reproduce?',
  ch08_heredity:             'Heredity and Evolution',
  ch10_light:                'Light — Reflection & Refraction',
  ch11_human_eye:            'Human Eye & Colourful World',
  ch12_electricity:          'Electricity',
  ch13_magnetic_effects:     'Magnetic Effects of Current',
  ch15_our_environment:      'Our Environment',
}

const SECTION_LABELS: Record<string, string> = {
  A: 'Section A — MCQ & Assertion-Reason (1m)',
  B: 'Section B — Short Answer I (2m)',
  C: 'Section C — Short Answer II (3m)',
  D: 'Section D — Long Answer (5m)',
  E: 'Section E — Case-Based (4m)',
}

function readinessBand(score: number): string {
  if (score >= 25) return 'Excellent'
  if (score >= 21) return 'Developing'
  if (score >= 15) return 'Needs Work'
  return 'Critical'
}

function readinessBandColor(score: number): string {
  if (score >= 25) return 'text-green-700 bg-green-50 border-green-200'
  if (score >= 21) return 'text-blue-700 bg-blue-50 border-blue-200'
  if (score >= 15) return 'text-amber-700 bg-amber-50 border-amber-200'
  return 'text-red-700 bg-red-50 border-red-200'
}

function ScoreBadge({ pct }: { pct: number }) {
  const color = pct >= 80 ? 'bg-green-100 text-green-700'
    : pct >= 50 ? 'bg-yellow-100 text-yellow-700'
    : 'bg-red-100 text-red-600'
  return <span className={`px-3 py-1 rounded-full text-sm font-semibold ${color}`}>{pct.toFixed(0)}%</span>
}

function FeedbackRow({ r }: { r: ExtendedQuestionResult }) {
  const [open, setOpen] = useState(false)
  const pct    = r.max_marks > 0 ? (r.score / r.max_marks) * 100 : 0
  const border = pct === 100 ? 'border-green-400' : pct >= 50 ? 'border-yellow-400' : 'border-red-400'
  const scoreBg = pct === 100 ? 'bg-green-50' : pct >= 50 ? 'bg-yellow-50' : 'bg-red-50'

  return (
    <div className={`border-l-4 ${border} bg-white rounded-r-xl shadow-sm mb-3`}>
      <button
        className="w-full text-left px-5 py-4 flex items-center justify-between"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex-1 mr-4">
          <div className="flex items-center gap-2 mb-1">
            {r.question_type && (
              <span className="text-xs text-gray-400 uppercase font-semibold">{r.question_type.replace('_', ' ')}</span>
            )}
          </div>
          <p className="text-sm text-gray-700 line-clamp-2">{r.question_text}</p>
        </div>
        <div className={`flex items-center gap-3 shrink-0 px-3 py-1 rounded-lg ${scoreBg}`}>
          <span className="font-bold text-gray-700">{r.score}/{r.max_marks}</span>
          <span className="text-gray-400 text-lg">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100 pt-4">
          {r.feedback?.comment && (
            <p className="text-gray-600 text-sm italic">{r.feedback.comment}</p>
          )}
          {r.student_answer != null && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Your Answer</p>
              <p className="text-sm text-gray-700 bg-gray-50 rounded p-2 whitespace-pre-wrap">{r.student_answer}</p>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Model Answer</p>
            <p className="text-sm text-gray-700 bg-gray-50 rounded p-2">{r.model_answer}</p>
          </div>
          {r.key_points?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase mb-1">Key Points</p>
              <ul className="list-disc list-inside space-y-1">
                {r.key_points.map((kp, i) => <li key={i} className="text-sm text-gray-700">{kp}</li>)}
              </ul>
            </div>
          )}
          {r.feedback?.points_missed?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-400 uppercase mb-1">Points Missed</p>
              <ul className="list-disc list-inside space-y-1">
                {r.feedback.points_missed.map((p, i) => <li key={i} className="text-sm text-red-600">{p}</li>)}
              </ul>
            </div>
          )}
          {r.suggestions && (
            <div className="bg-blue-50 rounded-lg p-3">
              <p className="text-xs font-semibold text-blue-400 uppercase mb-1">Improvement Tip</p>
              <p className="text-sm text-blue-700">{r.suggestions}</p>
            </div>
          )}
          <p className="text-xs text-gray-400">Evaluated by: {r.evaluation_layer}</p>
        </div>
      )}
    </div>
  )
}

function MarksLostSummary({ results }: { results: ExtendedQuestionResult[] }) {
  const byType: Record<string, { lost: number; total: number }> = {}
  for (const r of results) {
    const t = r.question_type ?? 'other'
    if (!byType[t]) byType[t] = { lost: 0, total: 0 }
    byType[t].lost  += Math.max(r.max_marks - r.score, 0)
    byType[t].total += r.max_marks
  }
  const entries = Object.entries(byType).filter(([, v]) => v.lost > 0)
  if (entries.length === 0) return null

  return (
    <div className="bg-white rounded-xl border shadow-sm p-5">
      <h2 className="font-semibold text-gray-700 mb-3">Marks Lost by Type</h2>
      <div className="space-y-2">
        {entries.map(([type, { lost, total }]) => (
          <div key={type} className="flex items-center justify-between">
            <span className="text-sm text-gray-600 capitalize">{type.replace('_', ' ')}</span>
            <span className="text-sm font-semibold text-red-600">−{lost.toFixed(1)} / {total}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SectionBreakdownCard({ breakdown }: { breakdown: Record<string, SectionBreakdown> }) {
  const sections = ['A', 'B', 'C', 'D', 'E'].filter(s => breakdown[s])
  if (sections.length === 0) return null
  return (
    <div className="bg-white rounded-xl border shadow-sm p-5">
      <h2 className="font-semibold text-gray-700 mb-4">Section-wise Breakdown</h2>
      <div className="space-y-3">
        {sections.map(sec => {
          const { score, max_marks } = breakdown[sec]
          const pct = max_marks > 0 ? (score / max_marks) * 100 : 0
          const bar = pct >= 80 ? 'bg-green-400' : pct >= 50 ? 'bg-yellow-400' : 'bg-red-400'
          return (
            <div key={sec}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 text-xs">{SECTION_LABELS[sec] ?? `Section ${sec}`}</span>
                <span className="font-semibold text-gray-700">{score.toFixed(1)}/{max_marks}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full">
                <div className={`h-2 rounded-full ${bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ChapterBreakdownCard({ breakdown }: { breakdown: Record<string, SectionBreakdown> }) {
  const chapters = Object.keys(breakdown).filter(ch => breakdown[ch].max_marks > 0)
  if (chapters.length === 0) return null
  return (
    <div className="bg-white rounded-xl border shadow-sm p-5">
      <h2 className="font-semibold text-gray-700 mb-4">Chapter-wise Breakdown</h2>
      <div className="space-y-3">
        {chapters.map(ch => {
          const { score, max_marks } = breakdown[ch]
          const pct = max_marks > 0 ? (score / max_marks) * 100 : 0
          const bar = pct >= 80 ? 'bg-green-400' : pct >= 50 ? 'bg-yellow-400' : 'bg-red-400'
          return (
            <div key={ch}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">{CHAPTER_LABELS[ch] ?? ch}</span>
                <span className="font-semibold text-gray-700">{score.toFixed(1)}/{max_marks}</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full">
                <div className={`h-2 rounded-full ${bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ExamReadinessCard({ score }: { score: number }) {
  const band  = readinessBand(score)
  const color = readinessBandColor(score)
  return (
    <div className={`rounded-xl border-2 p-5 ${color}`}>
      <p className="text-xs font-semibold uppercase opacity-70 mb-1">Exam Readiness Estimate</p>
      <div className="flex items-baseline gap-3">
        <p className="text-3xl font-black">{score.toFixed(1)}<span className="text-lg font-normal opacity-60">/30</span></p>
        <span className={`text-sm font-bold px-3 py-1 rounded-full border ${color}`}>{band}</span>
      </div>
      <p className="text-xs opacity-70 mt-2">
        Projected Physics board score (out of 30) based on your topic performance.
      </p>
    </div>
  )
}

export default function Results() {
  const { id }   = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()

  const stateResults = (location.state as { results?: ExtendedResults })?.results ?? null
  const [results,     setResults]    = useState<ExtendedResults | null>(stateResults)
  const [loading,     setLoading]    = useState(!stateResults)
  const [error,       setError]      = useState('')
  const [hasActive,   setHasActive]  = useState(false)
  const [celebrationDone, setCelebrationDone] = useState(false)
  const newBadges: string[] = (location.state as any)?.new_badges ?? []
  const leveledUp: boolean  = (location.state as any)?.leveled_up ?? false
  const newLevel: number    = (location.state as any)?.current_level ?? 1

  useEffect(() => {
    if (!results && id) {
      getResults(id)
        .then(r => setResults(r as ExtendedResults))
        .catch(e => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [id, results])

  useEffect(() => {
    getActiveSession().then(r => {
      setHasActive(
        !!r.active_session_id &&
        (r.status === 'in_progress' || r.status === 'awaiting_upload')
      )
    }).catch(() => {})
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading results…</div>
  if (error)   return <div className="p-8 text-center text-red-500">{error}</div>
  if (!results) return null

  const isMock        = results.type === 'mock'
  const isChapterTest = results.type === 'chapter_short' || results.type === 'chapter_regular'
  const isPaperTest   = isChapterTest || isMock
  const topicEntries  = Object.entries(results.topic_scores ?? {})
  const qResults      = (results.results ?? []) as ExtendedQuestionResult[]

  // Badge/level celebration modal
  if (!celebrationDone && (newBadges.length > 0 || leveledUp)) {
    return (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-full text-center">
          {leveledUp && (
            <div className="mb-4">
              <div className="text-5xl mb-2">🎉</div>
              <h2 className="text-2xl font-bold text-blue-700">Level Up!</h2>
              <p className="text-gray-600 mt-1">You reached <span className="font-bold text-blue-600">Level {newLevel}</span>!</p>
            </div>
          )}
          {newBadges.length > 0 && (
            <div className={leveledUp ? 'mt-4 border-t pt-4' : ''}>
              {!leveledUp && <div className="text-5xl mb-2">🏅</div>}
              <h2 className="text-xl font-bold text-amber-700">
                {newBadges.length === 1 ? 'Badge Unlocked!' : `${newBadges.length} Badges Unlocked!`}
              </h2>
              <div className="flex flex-wrap justify-center gap-2 mt-3">
                {newBadges.map(bid => (
                  <span key={bid} className="text-xs bg-amber-100 text-amber-800 border border-amber-200 px-2 py-1 rounded-full font-medium">
                    {bid.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                ))}
              </div>
            </div>
          )}
          <button
            onClick={() => setCelebrationDone(true)}
            className="mt-6 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition"
          >
            See Results →
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-16">
      <div className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-bold text-gray-800">
          {isMock ? 'Full Mock Test Results' : isChapterTest ? 'Chapter Test Results' : 'Session Results'}
        </h1>
        <p className="text-sm text-gray-500">
          {isMock
            ? 'All 13 Science Chapters · 39 questions · 80 marks'
            : `${results.chapter}${results.topic ? ` · ${results.topic}` : ''}${isChapterTest ? (results.type === 'chapter_short' ? ' · Short Test' : ' · Regular Test') : ''}`
          }
        </p>
      </div>

      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Score card */}
        <div className="bg-white rounded-xl shadow-sm border p-6 flex flex-wrap gap-6 items-center">
          <div className="text-center">
            <p className="text-5xl font-black text-gray-800">
              {typeof results.score_obtained === 'number' ? results.score_obtained.toFixed(1) : results.score_obtained}
              <span className="text-2xl text-gray-400">/{results.total_marks}</span>
            </p>
            <div className="mt-2">
              <ScoreBadge pct={results.percentage} />
            </div>
          </div>
          <div className="flex-1 grid grid-cols-2 gap-4 text-center min-w-48">
            <div className="bg-purple-50 rounded-lg p-3">
              <p className="text-2xl font-bold text-purple-600">+{results.xp_earned ?? 0}</p>
              <p className="text-xs text-purple-400 uppercase font-semibold">XP Earned</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-3">
              <p className="text-2xl font-bold text-orange-600">{results.current_streak}</p>
              <p className="text-xs text-orange-400 uppercase font-semibold">Day Streak</p>
            </div>
            <div className="col-span-2 bg-gray-50 rounded-lg p-3">
              <p className="text-lg font-bold text-gray-700">{results.total_xp} XP total</p>
            </div>
          </div>
        </div>

        {/* Exam readiness — mock only */}
        {isMock && results.exam_readiness_score != null && (
          <ExamReadinessCard score={results.exam_readiness_score} />
        )}

        {/* Section breakdown — mock only */}
        {isMock && results.section_breakdown && (
          <SectionBreakdownCard breakdown={results.section_breakdown} />
        )}

        {/* Chapter breakdown — mock only */}
        {isMock && results.chapter_breakdown && (
          <ChapterBreakdownCard breakdown={results.chapter_breakdown} />
        )}

        {/* Marks lost by type — chapter tests only */}
        {isChapterTest && <MarksLostSummary results={qResults} />}

        {/* Topic scores */}
        {topicEntries.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="font-semibold text-gray-700 mb-4">Topic Performance</h2>
            <div className="space-y-3">
              {topicEntries.map(([topic, score]) => {
                const pct = typeof score === 'number' ? score : 0
                const bar = pct >= 80 ? 'bg-green-400' : pct >= 50 ? 'bg-yellow-400' : 'bg-red-400'
                return (
                  <div key={topic}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">{topic}</span>
                      <span className="font-semibold text-gray-700">{pct.toFixed(0)}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full">
                      <div className={`h-2 rounded-full ${bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Overall guidance */}
        {results.overall_guidance && (
          <div className={`border rounded-xl p-5 ${isMock ? 'bg-purple-50 border-purple-100' : 'bg-indigo-50 border-indigo-100'}`}>
            <p className={`text-xs font-semibold uppercase mb-2 ${isMock ? 'text-purple-400' : 'text-indigo-400'}`}>
              {isMock ? 'Mock Test Guidance' : 'Overall Guidance'}
            </p>
            <p className={`text-sm leading-relaxed ${isMock ? 'text-purple-800' : 'text-indigo-800'}`}>
              {results.overall_guidance}
            </p>
          </div>
        )}

        {/* Per-question breakdown */}
        <div>
          <h2 className="font-semibold text-gray-700 mb-3">Question Breakdown</h2>
          {qResults.map(r => <FeedbackRow key={r.question_id} r={r} />)}
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex-1 py-3 border border-gray-300 rounded-xl text-gray-700 font-semibold"
          >
            Home
          </button>
          {isPaperTest ? (
            <button
              onClick={() => navigate('/session/new')}
              disabled={hasActive}
              title={hasActive ? 'Another test is active' : ''}
              className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-semibold disabled:opacity-40"
            >
              {hasActive ? 'Test Active' : isMock ? 'New Mock / Test' : 'Retake Test'}
            </button>
          ) : (
            <button
              onClick={() => navigate('/session/new')}
              className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-semibold"
            >
              New Session
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
