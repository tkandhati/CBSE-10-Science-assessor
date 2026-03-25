import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAdminDashboard } from '../../api/client'
import type { AdminDashboardData, ChapterPerf } from '../../types'

const CHAPTER_ORDER = [
  'ch01_chemical_reactions', 'ch02_acids_bases_salts', 'ch03_metals_non_metals', 'ch04_carbon_compounds',
  'ch05_life_processes', 'ch06_control_coordination', 'ch07_reproduction', 'ch08_heredity',
  'ch10_light', 'ch11_human_eye', 'ch12_electricity', 'ch13_magnetic_effects', 'ch15_our_environment',
]

const CHAPTER_LABELS: Record<string, string> = {
  ch01_chemical_reactions:   'Chemical Reactions & Equations',
  ch02_acids_bases_salts:    'Acids, Bases and Salts',
  ch03_metals_non_metals:    'Metals and Non-Metals',
  ch04_carbon_compounds:     'Carbon and its Compounds',
  ch05_life_processes:       'Life Processes',
  ch06_control_coordination: 'Control and Coordination',
  ch07_reproduction:         'How do Organisms Reproduce?',
  ch08_heredity:             'Heredity and Evolution',
  ch10_light:                'Light — Reflection and Refraction',
  ch11_human_eye:            'Human Eye and Colourful World',
  ch12_electricity:          'Electricity',
  ch13_magnetic_effects:     'Magnetic Effects of Current',
  ch15_our_environment:      'Our Environment',
}

const CHAPTER_SUBJECT: Record<string, string> = {
  ch01_chemical_reactions: 'Chemistry', ch02_acids_bases_salts: 'Chemistry',
  ch03_metals_non_metals: 'Chemistry',  ch04_carbon_compounds: 'Chemistry',
  ch05_life_processes: 'Biology',       ch06_control_coordination: 'Biology',
  ch07_reproduction: 'Biology',         ch08_heredity: 'Biology',
  ch10_light: 'Physics',                ch11_human_eye: 'Physics',
  ch12_electricity: 'Physics',          ch13_magnetic_effects: 'Physics',
  ch15_our_environment: 'Env. Science',
}

const BAND_COLOR: Record<string, string> = {
  Strong:      'bg-green-500',
  Developing:  'bg-amber-400',
  Weak:        'bg-orange-500',
  Critical:    'bg-red-600',
  Untested:    'bg-gray-300',
}

const BAND_TEXT: Record<string, string> = {
  Strong:      'text-green-700 bg-green-50 border-green-200',
  Developing:  'text-amber-700 bg-amber-50 border-amber-200',
  Weak:        'text-orange-700 bg-orange-50 border-orange-200',
  Critical:    'text-red-700 bg-red-50 border-red-200',
  Untested:    'text-gray-500 bg-gray-50 border-gray-200',
}

function BandPill({ band }: { band: string }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${BAND_TEXT[band] ?? 'text-gray-500 bg-gray-50 border-gray-200'}`}>
      {band}
    </span>
  )
}

function MetricCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function ChapterBar({ id, data }: { id: string; data: ChapterPerf }) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.min(100, data.average)

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-gray-700">{data.title}</span>
            <div className="flex items-center gap-2">
              <BandPill band={data.band} />
              <span className="text-sm font-bold text-gray-700">{data.average}%</span>
              <span className="text-xs text-gray-400">{data.attempts} Q</span>
            </div>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${BAND_COLOR[data.band] ?? 'bg-gray-300'}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <span className="text-gray-400 text-sm">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="border-t bg-gray-50 px-4 py-3 text-sm text-gray-500">
          <p>Chapter detail available in Topic Intelligence →</p>
          <a href="/admin/strengths" className="text-blue-600 underline text-xs">View all topics for {data.title}</a>
        </div>
      )}
    </div>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })
}

function formatType(type: string) {
  const map: Record<string, string> = {
    understanding: 'Understanding',
    chapter_short: 'Short Test',
    chapter_regular: 'Regular Test',
    mock: 'Mock Test',
  }
  return map[type] ?? type
}

export default function AdminDashboard({ showSessionsExpanded = false }: { showSessionsExpanded?: boolean }) {
  const navigate = useNavigate()
  const [data, setData] = useState<AdminDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    getAdminDashboard()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-400 text-sm mt-8 text-center">Loading dashboard…</div>
  if (error)   return <div className="text-red-500 text-sm mt-8 text-center">{error}</div>
  if (!data)   return null

  return (
    <div className="max-w-5xl mx-auto pb-16">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Admin Dashboard</h1>

      {/* Metrics strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-8">
        <MetricCard label="Sessions" value={data.total_sessions} />
        <MetricCard label="Questions Answered" value={data.total_questions_answered} />
        <MetricCard label="Overall Average" value={`${data.overall_average}%`} />
        <MetricCard label="Current Streak" value={data.current_streak} sub="days" />
        <MetricCard label="Best Streak" value={data.best_streak} sub="days" />
      </div>

      {/* Coverage gap alert */}
      {data.coverage_gaps.length > 0 && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-sm">
          <p className="font-semibold mb-1">Question Bank Gaps Detected</p>
          <p>{data.coverage_gaps.length} slot(s) have insufficient questions for full paper generation.</p>
          <a href="/admin/questions" className="text-amber-700 underline text-xs">Go to Question Bank →</a>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Chapter performance bars */}
        <div className="lg:col-span-2">
          <h2 className="text-base font-semibold text-gray-700 mb-3">Chapter Performance</h2>
          <div className="space-y-2">
            {CHAPTER_ORDER.map(id => {
              const d = data.chapter_performance[id]
              return d ? <ChapterBar key={id} id={id} data={d} /> : null
            })}
          </div>
        </div>

        {/* Side panels */}
        <div className="space-y-4">
          {/* Exam readiness */}
          {data.exam_readiness && (
            <div className="bg-white rounded-xl border p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Exam Readiness</h2>
              <div className="flex items-baseline gap-1 mb-1">
                <span className="text-3xl font-bold text-gray-800">{data.exam_readiness.score}</span>
                <span className="text-gray-400 text-sm">/ {(data.exam_readiness as any).max_marks ?? 84}</span>
              </div>
              <p className="text-xs text-gray-400 mb-2">
                Range: {data.exam_readiness.range_low}–{data.exam_readiness.range_high}
              </p>
              <BandPill band={data.exam_readiness.band_label} />
            </div>
          )}

          {/* Strengths */}
          {data.strengths.length > 0 && (
            <div className="bg-white rounded-xl border p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Top Strengths</h2>
              <div className="flex flex-wrap gap-2">
                {data.strengths.map(s => (
                  <span key={s.topic_key} className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700 border border-green-200">
                    {s.topic_key.split('.')[1]?.replace(/_/g, ' ') ?? s.topic_key} · {s.score}%
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Weaknesses */}
          {data.weaknesses.length > 0 && (
            <div className="bg-white rounded-xl border p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Needs Work</h2>
              <div className="flex flex-wrap gap-2">
                {data.weaknesses.map(w => (
                  <span key={w.topic_key} className="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700 border border-red-200">
                    {w.topic_title} · {w.score}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent sessions */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">Recent Sessions</h2>
      {data.recent_sessions.length === 0 ? (
        <p className="text-gray-400 text-sm">No completed sessions yet.</p>
      ) : (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Date</th>
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Type</th>
                <th className="text-left px-4 py-2 text-gray-500 font-medium">Chapter</th>
                <th className="text-right px-4 py-2 text-gray-500 font-medium">Score</th>
                <th className="text-right px-4 py-2 text-gray-500 font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_sessions.map((s, i) => (
                <tr
                  key={s.id}
                  className={`border-b last:border-0 hover:bg-blue-50 cursor-pointer transition-colors ${i % 2 === 0 ? '' : 'bg-gray-50/40'}`}
                  onClick={() => navigate(`/admin/session/${s.id}`)}
                >
                  <td className="px-4 py-2 text-gray-600">{formatDate(s.started_at)}</td>
                  <td className="px-4 py-2">
                    <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                      {formatType(s.type)}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-gray-600">{s.chapter === 'all' ? 'All chapters' : s.chapter}</td>
                  <td className="px-4 py-2 text-right font-semibold text-gray-700">
                    {s.score_obtained}/{s.total_marks}
                    <span className="text-gray-400 font-normal ml-1">({s.percentage}%)</span>
                  </td>
                  <td className="px-4 py-2 text-right text-gray-400">
                    {s.duration_seconds ? `${Math.round(s.duration_seconds / 60)} min` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
