import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAdminDashboard, getTopicStrengths, getAdminSessions, getActiveSession } from '../api/client'
import type { AdminDashboardData, TopicStrengthsData } from '../types'

interface StudentProfile {
  name: string
  total_xp: number
  current_level: number
  xp_in_level: number
  xp_to_next_level: number
  xp_per_level: number
  current_streak: number
  best_streak: number
  badges: string[]
  exam_readiness_score: number
}

interface BadgeInfo {
  id: string; name: string; description: string; icon: string
  earned: boolean; earned_at: string | null
}

const CHAPTER_ORDER = [
  'ch01_chemical_reactions', 'ch02_acids_bases_salts', 'ch03_metals_non_metals', 'ch04_carbon_compounds',
  'ch05_life_processes', 'ch06_control_coordination', 'ch07_reproduction', 'ch08_heredity',
  'ch10_light', 'ch11_human_eye', 'ch12_electricity', 'ch13_magnetic_effects', 'ch15_our_environment',
]
const CHAPTER_LABELS: Record<string, string> = {
  ch01_chemical_reactions:   'Chem. Reactions',
  ch02_acids_bases_salts:    'Acids & Bases',
  ch03_metals_non_metals:    'Metals',
  ch04_carbon_compounds:     'Carbon Cmpds',
  ch05_life_processes:       'Life Processes',
  ch06_control_coordination: 'Control & Coord',
  ch07_reproduction:         'Reproduction',
  ch08_heredity:             'Heredity',
  ch10_light:                'Light',
  ch11_human_eye:            'Human Eye',
  ch12_electricity:          'Electricity',
  ch13_magnetic_effects:     'Magnetic Effects',
  ch15_our_environment:      'Our Environment',
}
const BAND_BG: Record<string, string> = {
  Strong: 'stroke-green-500', Developing: 'stroke-amber-400',
  Weak: 'stroke-orange-500', Critical: 'stroke-red-600', Untested: 'stroke-gray-300',
}
const SESSION_LABEL: Record<string, string> = {
  understanding: 'Understanding', chapter_short: 'Short Test',
  chapter_regular: 'Regular Test', mock: 'Mock Test',
}

function ProgressRing({ pct, band, size = 64 }: { pct: number; band: string; size?: number }) {
  const r = (size - 10) / 2
  const circ = 2 * Math.PI * r
  const dash = Math.min(pct / 100, 1) * circ
  const stroke = BAND_BG[band] ?? 'stroke-gray-300'
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={8} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none"
        className={stroke} strokeWidth={8}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
      />
    </svg>
  )
}

function XPBar({ xpInLevel, xpPerLevel }: { xpInLevel: number; xpPerLevel: number }) {
  const pct = Math.round((xpInLevel / xpPerLevel) * 100)
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{xpInLevel} XP</span>
        <span>{xpPerLevel} XP</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function BadgeShelf({ badges }: { badges: BadgeInfo[] }) {
  const [tooltip, setTooltip] = useState<string | null>(null)
  return (
    <div>
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Badges</h2>
      <div className="flex flex-wrap gap-3">
        {badges.map(b => (
          <div
            key={b.id}
            className="relative"
            onMouseEnter={() => setTooltip(b.id)}
            onMouseLeave={() => setTooltip(null)}
          >
            <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl border-2 transition-all
              ${b.earned
                ? 'bg-yellow-50 border-yellow-300 shadow-sm'
                : 'bg-gray-100 border-gray-200 opacity-40 grayscale'
              }`}>
              {b.icon}
            </div>
            {tooltip === b.id && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-40 bg-gray-900 text-white text-xs rounded-lg p-2 z-10 text-center shadow-lg">
                <p className="font-semibold mb-0.5">{b.name}</p>
                <p className="text-gray-300">{b.description}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [profile, setProfile]   = useState<StudentProfile | null>(null)
  const [badges,  setBadges]    = useState<BadgeInfo[]>([])
  const [dash,    setDash]      = useState<AdminDashboardData | null>(null)
  const [topics,  setTopics]    = useState<TopicStrengthsData | null>(null)
  const [recentSessions, setRecentSessions] = useState<any[]>([])
  const [activeTestId, setActiveTestId] = useState<string | null>(null)
  const [loading, setLoading]   = useState(true)
  const [error,   setError]     = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/student/profile').then(r => r.ok ? r.json() : null),
      fetch('/api/student/badges').then(r => r.ok ? r.json() : { badges: [] }),
      getAdminDashboard().catch(() => null),
      getTopicStrengths().catch(() => null),
      getAdminSessions({ limit: 5 }).catch(() => ({ sessions: [] })),
      getActiveSession().catch(() => ({ active_session_id: null })),
    ]).then(([prof, bdg, d, t, sess, active]) => {
      if (prof) setProfile(prof)
      setBadges((bdg?.badges ?? []) as BadgeInfo[])
      if (d) setDash(d)
      if (t) setTopics(t)
      setRecentSessions((sess as any)?.sessions ?? [])
      if ((active as any)?.active_session_id) {
        setActiveTestId((active as any).active_session_id)
      }
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-gray-400 text-sm">Loading dashboard…</div>
    </div>
  )
  if (error) return <div className="text-red-500 text-sm mt-8 text-center">{error}</div>

  return (
    <div className="max-w-5xl mx-auto pb-16">
      {/* Profile strip */}
      <div className="bg-white rounded-xl border p-5 mb-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-gray-800 mb-1">
              {profile?.name ?? 'Student'}
            </h1>
            <div className="flex items-center gap-4 text-sm text-gray-500 mb-3 flex-wrap">
              <span className="font-semibold text-blue-700 bg-blue-50 px-3 py-1 rounded-full">
                Level {profile?.current_level ?? 1}
              </span>
              <span className="flex items-center gap-1">
                🔥 <span className="font-semibold text-orange-600">{profile?.current_streak ?? 0}</span>
                <span className="text-gray-400">day streak</span>
              </span>
              <span className="text-gray-400">Best: {profile?.best_streak ?? 0} days</span>
            </div>
            {profile && (
              <div className="max-w-xs">
                <XPBar xpInLevel={profile.xp_in_level} xpPerLevel={profile.xp_per_level} />
                <p className="text-xs text-gray-400 mt-1">{profile.total_xp} total XP · {profile.xp_to_next_level} to Level {profile.current_level + 1}</p>
              </div>
            )}
          </div>

          {/* Exam readiness */}
          {profile && profile.exam_readiness_score > 0 && (
            <div className="text-center shrink-0">
              <p className="text-xs text-gray-400 mb-1">Exam Readiness</p>
              <p className="text-3xl font-bold text-gray-800">{profile.exam_readiness_score}</p>
              <p className="text-xs text-gray-400">/ 30</p>
            </div>
          )}
        </div>

        {/* Streak message */}
        {(profile?.current_streak ?? 0) > 0 && (
          <div className="mt-3 text-sm text-orange-600 font-medium">
            🔥 {profile!.current_streak} day streak — keep going!
          </div>
        )}
      </div>

      {/* Quick start */}
      <div className="mb-6">
        <h2 className="text-base font-semibold text-gray-700 mb-3">Quick Start</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Understanding Session', sub: '10–12 Q · instant feedback', color: 'border-blue-500 bg-blue-50 text-blue-700', to: '/session/new' },
            { label: 'Chapter Test', sub: '14–40 marks · write on paper', color: 'border-amber-500 bg-amber-50 text-amber-700', to: '/session/new' },
            { label: 'Full Mock Test', sub: '80 marks · 3 hours', color: 'border-purple-500 bg-purple-50 text-purple-700', to: '/session/new' },
          ].map(btn => (
            <button
              key={btn.label}
              onClick={() => navigate(activeTestId ? `/session/${activeTestId}` : btn.to)}
              className={`p-4 rounded-xl border-2 text-left transition-all hover:shadow-sm ${btn.color}`}
            >
              <p className="font-semibold text-sm">{activeTestId ? `▶ Resume Test` : btn.label}</p>
              <p className="text-xs mt-0.5 opacity-70">{activeTestId ? 'An active test is in progress' : btn.sub}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Chapter progress rings */}
        <div className="lg:col-span-2">
          <h2 className="text-base font-semibold text-gray-700 mb-3">Chapter Progress</h2>
          <div className="bg-white rounded-xl border p-4 grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-7 gap-4">
            {CHAPTER_ORDER.map(chId => {
              const perf = dash?.chapter_performance?.[chId]
              const chTopics = topics ? Object.entries(topics.topics).filter(([,t]) => t.chapter_id === chId) : []
              const devAbove = chTopics.filter(([,t]) => t.band !== 'Untested' && t.band !== 'Critical' && t.band !== 'Weak').length
              const coverage = chTopics.length > 0 ? Math.round(devAbove / chTopics.length * 100) : 0
              const band = perf?.band ?? 'Untested'
              return (
                <div key={chId} className="flex flex-col items-center gap-2 text-center">
                  <div className="relative">
                    <ProgressRing pct={coverage} band={band} size={64} />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold text-gray-600">{coverage}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600 leading-tight">{CHAPTER_LABELS[chId]}</p>
                </div>
              )
            })}
          </div>
        </div>

        {/* Streak + readiness side panel */}
        <div className="space-y-4">
          {dash?.exam_readiness && (
            <div className="bg-white rounded-xl border p-4">
              <p className="text-xs text-gray-400 mb-1">Board Score Estimate</p>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold text-gray-800">{dash.exam_readiness.score}</span>
                <span className="text-gray-400 text-sm">– {dash.exam_readiness.range_high} / 30</span>
              </div>
              <p className="text-xs font-medium mt-1">
                <span className={`px-2 py-0.5 rounded-full text-xs border
                  ${dash.exam_readiness.band_label === 'Excellent' ? 'text-green-700 bg-green-50 border-green-200' :
                    dash.exam_readiness.band_label === 'Good' ? 'text-blue-700 bg-blue-50 border-blue-200' :
                    'text-amber-700 bg-amber-50 border-amber-200'}`}>
                  {dash.exam_readiness.band_label}
                </span>
              </p>
            </div>
          )}
          {dash && (
            <div className="bg-white rounded-xl border p-4 text-sm">
              <div className="flex justify-between mb-2">
                <span className="text-gray-500">Sessions</span>
                <span className="font-semibold text-gray-700">{dash.total_sessions}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Questions</span>
                <span className="font-semibold text-gray-700">{dash.total_questions_answered}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent sessions */}
      <div className="mb-6">
        <h2 className="text-base font-semibold text-gray-700 mb-3">Recent Sessions</h2>
        {recentSessions.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center">
            <p className="text-gray-400 text-sm">No sessions yet — start your first session!</p>
            <button onClick={() => navigate('/session/new')}
              className="mt-3 text-blue-600 text-sm underline">Start a session →</button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-gray-400 text-xs">
                  <th className="text-left px-4 py-2 font-medium">Date</th>
                  <th className="text-left px-4 py-2 font-medium">Type</th>
                  <th className="text-left px-4 py-2 font-medium hidden sm:table-cell">Chapter</th>
                  <th className="text-right px-4 py-2 font-medium">Score</th>
                </tr>
              </thead>
              <tbody>
                {recentSessions.map((s: any, i: number) => (
                  <tr key={s.id}
                    className={`border-b last:border-0 hover:bg-blue-50 cursor-pointer transition-colors ${i % 2 === 0 ? '' : 'bg-gray-50/40'}`}
                    onClick={() => navigate(`/session/${s.id}/results`)}>
                    <td className="px-4 py-2 text-gray-500">{formatDate(s.started_at)}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                        {SESSION_LABEL[s.type] ?? s.type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 hidden sm:table-cell">
                      {s.chapter === 'all' ? 'All chapters' : (CHAPTER_LABELS[s.chapter] ?? s.chapter)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <span className={`font-semibold ${s.percentage >= 80 ? 'text-green-700' : s.percentage >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                        {s.percentage}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Badge shelf */}
      {badges.length > 0 && (
        <div className="bg-white rounded-xl border p-5">
          <BadgeShelf badges={badges} />
        </div>
      )}
    </div>
  )
}
