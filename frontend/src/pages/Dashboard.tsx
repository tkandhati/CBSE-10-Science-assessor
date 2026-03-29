import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAdminDashboard, getTopicStrengths, getAdminSessions, sparkTodayStatus, getCountdown } from '../api/client'
import type { AdminDashboardData, TopicStrengthsData } from '../types'
import type { CountdownData } from '../api/client'

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

const PACE_STYLE: Record<string, string> = {
  'Getting Started': 'text-gray-600 bg-gray-100 border-gray-200',
  'Behind':          'text-red-700   bg-red-50   border-red-200',
  'On Track':        'text-green-700 bg-green-50 border-green-200',
  'Ahead':           'text-blue-700  bg-blue-50  border-blue-200',
}

function CountdownWidget({ data }: { data: CountdownData }) {
  const { days_remaining, projected_score, projected_max, pace_label,
          weekly_target, weekly_done, advice } = data

  const weeks = Math.floor(days_remaining / 7)
  const scorePct = Math.round(projected_score / projected_max * 100)

  function Pips({ done, total }: { done: number; total: number }) {
    return (
      <span className="inline-flex gap-0.5 ml-1">
        {Array.from({ length: total }).map((_, i) => (
          <span key={i} className={`inline-block w-2 h-2 rounded-full ${i < done ? 'bg-current' : 'bg-gray-300'}`} />
        ))}
      </span>
    )
  }

  return (
    <div className="mb-6 bg-white rounded-xl border px-5 py-4 flex flex-wrap items-center gap-x-6 gap-y-3">
      {/* Days block */}
      <div className="flex items-baseline gap-1.5 shrink-0">
        <span className="text-3xl font-bold text-gray-800">{days_remaining}</span>
        <span className="text-xs text-gray-400 leading-tight">days to<br />board exam</span>
      </div>

      <div className="w-px h-10 bg-gray-200 hidden sm:block" />

      {/* Projected score */}
      <div className="shrink-0">
        <p className="text-xs text-gray-400 mb-0.5">Projected score</p>
        <p className="text-sm font-semibold text-gray-700">
          {projected_score} <span className="text-gray-400 font-normal">/ {projected_max}</span>
          <span className="ml-1.5 text-xs text-gray-400">({scorePct}%)</span>
        </p>
      </div>

      <div className="w-px h-10 bg-gray-200 hidden sm:block" />

      {/* Pace + weeks */}
      <div className="shrink-0">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${PACE_STYLE[pace_label] ?? PACE_STYLE['On Track']}`}>
          {pace_label}
        </span>
        <p className="text-xs text-gray-400 mt-1">{weeks} weeks left</p>
      </div>

      <div className="w-px h-10 bg-gray-200 hidden sm:block" />

      {/* Weekly targets */}
      <div className="shrink-0">
        <p className="text-xs text-gray-400 mb-1">This week</p>
        <div className="flex gap-4 text-xs text-gray-600">
          <span>
            Understanding
            <Pips done={Math.min(weekly_done.understanding, weekly_target.understanding)} total={weekly_target.understanding} />
          </span>
          <span>
            Chapter Test
            <Pips done={Math.min(weekly_done.chapter_test, weekly_target.chapter_test)} total={weekly_target.chapter_test} />
          </span>
        </div>
      </div>

      {/* Advice */}
      <p className="text-xs text-gray-500 italic w-full sm:w-auto sm:flex-1">{advice}</p>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [profile, setProfile]   = useState<StudentProfile | null>(null)
  const [badges,  setBadges]    = useState<BadgeInfo[]>([])
  const [dash,    setDash]      = useState<AdminDashboardData | null>(null)
  const [topics,  setTopics]    = useState<TopicStrengthsData | null>(null)
  const [recentSessions, setRecentSessions] = useState<any[]>([])
  const [sparkDone,    setSparkDone]    = useState(false)
  const [countdown,    setCountdown]    = useState<CountdownData | null>(null)
  const [loading, setLoading]   = useState(true)
  const [error,   setError]     = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/student/profile').then(r => r.ok ? r.json() : null),
      fetch('/api/student/badges').then(r => r.ok ? r.json() : { badges: [] }),
      getAdminDashboard().catch(() => null),
      getTopicStrengths().catch(() => null),
      getAdminSessions({ limit: 6 }).catch(() => ({ sessions: [] })),
      sparkTodayStatus().catch(() => ({ completed_today: false })),
      getCountdown().catch(() => null),
    ]).then(([prof, bdg, d, t, sess, spark, cd]) => {
      if (prof) setProfile(prof)
      setBadges((bdg?.badges ?? []) as BadgeInfo[])
      if (d) setDash(d)
      if (t) setTopics(t)
      setRecentSessions(((sess as any)?.sessions ?? []).filter((s: any) => s.type !== 'spark'))
      setSparkDone((spark as any)?.completed_today ?? false)
      if (cd) setCountdown(cd as CountdownData)
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

      {/* Daily Spark banner */}
      <div className={`mb-6 rounded-xl border-2 p-4 flex items-center justify-between gap-4
        ${sparkDone
          ? 'border-green-300 bg-green-50'
          : 'border-amber-400 bg-amber-50'}`}>
        <div className="flex items-center gap-3">
          <span className="text-2xl">{sparkDone ? '✅' : '⚡'}</span>
          <div>
            <p className="font-semibold text-sm text-gray-800">
              {sparkDone ? "Spark done today!" : "Daily Spark — 10 quick questions"}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              {sparkDone
                ? 'Streak safe. Want another round?'
                : '5 min · MCQ only · keeps your streak alive'}
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/spark')}
          className={`shrink-0 text-sm font-semibold px-4 py-2 rounded-lg transition-colors
            ${sparkDone
              ? 'bg-green-600 hover:bg-green-700 text-white'
              : 'bg-amber-500 hover:bg-amber-600 text-white'}`}
        >
          {sparkDone ? 'Another Spark' : 'Start Spark'}
        </button>
      </div>

      {/* Board exam countdown */}
      {countdown && <CountdownWidget data={countdown} />}


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
                <span className="text-gray-500">Tests</span>
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
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">Recent Tests</h2>
          <button
            onClick={() => navigate('/session/new')}
            className="text-sm font-semibold px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            + New Test
          </button>
        </div>
        {recentSessions.length === 0 ? (
          <div className="bg-white rounded-xl border p-8 text-center">
            <p className="text-gray-400 text-sm">No tests yet — start your first test!</p>
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
                  <th className="text-right px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {recentSessions.map((s: any, i: number) => {
                  const isActive = s.status === 'in_progress' || s.status === 'awaiting_upload'
                  return (
                  <tr key={s.id}
                    className={`border-b last:border-0 hover:bg-blue-50 transition-colors ${i % 2 === 0 ? '' : 'bg-gray-50/40'}`}>
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
                      {!isActive && (
                        <span className={`font-semibold ${s.percentage >= 80 ? 'text-green-700' : s.percentage >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                          {s.percentage}%
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {isActive ? (
                        <button
                          onClick={() => navigate(`/session/${s.id}`)}
                          className="text-xs text-amber-600 hover:text-amber-800 font-semibold underline underline-offset-2"
                        >
                          Resume
                        </button>
                      ) : (
                        <button
                          onClick={() => navigate(`/session/${s.id}/results`)}
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium underline underline-offset-2"
                        >
                          Review
                        </button>
                      )}
                    </td>
                  </tr>
                  )
                })}
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
