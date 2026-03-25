import { useEffect, useState } from 'react'
import { getTopicStrengths } from '../../api/client'
import type { TopicStrengthsData, TopicInfo } from '../../types'

const CHAPTER_ORDER = ['light', 'human_eye', 'electricity', 'magnetic_effects', 'sources_of_energy']

const BAND_PILL: Record<string, string> = {
  Strong:     'text-green-700 bg-green-50 border-green-200',
  Developing: 'text-amber-700 bg-amber-50 border-amber-200',
  Weak:       'text-orange-700 bg-orange-50 border-orange-200',
  Critical:   'text-red-700 bg-red-50 border-red-200',
  Untested:   'text-gray-500 bg-gray-50 border-gray-200',
}

const ACTION_PILL: Record<string, string> = {
  'Revise Now':         'bg-red-100 text-red-700',
  'Practice More':      'bg-orange-100 text-orange-700',
  'Consolidate':        'bg-amber-100 text-amber-700',
  'Keep Going':         'bg-green-100 text-green-700',
  'Maintain':           'bg-green-50 text-green-600',
  'Start Practising':   'bg-blue-100 text-blue-700',
}

const TREND_ARROW: Record<string, { icon: string; color: string }> = {
  up:   { icon: '↑', color: 'text-green-600' },
  down: { icon: '↓', color: 'text-red-500' },
  flat: { icon: '→', color: 'text-gray-400' },
}

function BandPill({ band }: { band: string }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${BAND_PILL[band] ?? 'text-gray-500 bg-gray-50 border-gray-200'}`}>
      {band}
    </span>
  )
}

function ActionBadge({ action }: { action: string }) {
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ACTION_PILL[action] ?? 'bg-gray-100 text-gray-600'}`}>
      {action}
    </span>
  )
}

function formatDate(d: string | null) {
  if (!d) return 'Never'
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function Sparkline({ data, trend }: { data: number[]; trend: string }) {
  if (!data || data.length < 2) {
    return <span className="text-gray-300 text-xs inline-block w-16 text-center">—</span>
  }
  const W = 64, H = 24, pad = 2
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (W - pad * 2)
    const y = H - pad - ((v - min) / range) * (H - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  const color = trend === 'up' ? '#16a34a' : trend === 'down' ? '#dc2626' : '#9ca3af'
  return (
    <svg width={W} height={H} className="overflow-visible inline-block">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function ChapterAccordion({
  chapterId,
  topics,
}: {
  chapterId: string
  topics: [string, TopicInfo][]
}) {
  const chapterTitle = topics[0]?.[1]?.chapter_title ?? chapterId
  const avgScore = topics.length
    ? Math.round(topics.reduce((s, [, t]) => s + t.score, 0) / topics.length)
    : 0
  const bands = topics.map(([, t]) => t.band)
  const hasWeak = bands.some(b => b === 'Weak' || b === 'Critical')

  const [open, setOpen] = useState(hasWeak)

  const bandForAvg = avgScore >= 80 ? 'Strong' : avgScore >= 60 ? 'Developing' : avgScore >= 40 ? 'Weak' : 'Critical'

  return (
    <div className="border rounded-xl overflow-hidden mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="font-semibold text-gray-800">{chapterTitle}</span>
          <BandPill band={bandForAvg} />
          <span className="text-sm text-gray-400">average {avgScore}% · {topics.length} topics</span>
        </div>
        <span className="text-gray-400">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t">
          <div className="hidden sm:grid grid-cols-12 gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-400 font-medium border-b">
            <div className="col-span-3">Topic</div>
            <div className="col-span-2">Band</div>
            <div className="col-span-1 text-center">Score</div>
            <div className="col-span-1 text-center">Attempts</div>
            <div className="col-span-1 text-center">Last Tested</div>
            <div className="col-span-2 text-center">Trend</div>
            <div className="col-span-2">Action</div>
          </div>
          {topics.map(([key, t]) => {
            const trend = TREND_ARROW[t.trend] ?? TREND_ARROW.flat
            return (
              <div
                key={key}
                className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b last:border-0 items-center hover:bg-gray-50/50 text-sm"
              >
                <div className="col-span-3 text-gray-700 font-medium">{t.topic_title}</div>
                <div className="col-span-2"><BandPill band={t.band} /></div>
                <div className="col-span-1 text-center font-semibold text-gray-700">
                  {t.band === 'Untested' ? '—' : `${t.score}%`}
                </div>
                <div className="col-span-1 text-center text-gray-500">{t.attempts}</div>
                <div className="col-span-1 text-center text-gray-400 text-xs">{formatDate(t.last_tested)}</div>
                <div className="col-span-2 flex items-center gap-1 justify-center">
                  <Sparkline data={(t as TopicInfo & { score_history?: number[] }).score_history ?? []} trend={t.trend} />
                  <span className={`text-base font-bold ${trend.color}`}>{trend.icon}</span>
                </div>
                <div className="col-span-2"><ActionBadge action={t.recommended_action} /></div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function TopicStrengths() {
  const [data, setData] = useState<TopicStrengthsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  useEffect(() => {
    getTopicStrengths()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-400 text-sm mt-8 text-center">Loading topic intelligence…</div>
  if (error)   return <div className="text-red-500 text-sm mt-8 text-center">{error}</div>
  if (!data)   return null

  // Group topics by chapter
  const byChapter: Record<string, [string, TopicInfo][]> = {}
  for (const [key, t] of Object.entries(data.topics)) {
    const ch = t.chapter_id
    if (!byChapter[ch]) byChapter[ch] = []
    byChapter[ch].push([key, t])
  }

  return (
    <div className="max-w-5xl mx-auto pb-16">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Topic Intelligence</h1>

      {/* Weak topics summary */}
      {data.weak_topics.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <h2 className="text-sm font-semibold text-red-800 mb-3">Top 5 Weakest Topics</h2>
          <div className="space-y-2">
            {data.weak_topics.map((w, i) => (
              <div key={w.topic_key} className="flex items-center gap-3 text-sm">
                <span className="text-red-400 font-bold w-4">{i + 1}</span>
                <span className="flex-1 text-red-900 font-medium">{w.topic_title}</span>
                <span className="text-red-500 text-xs">{w.chapter_title}</span>
                <span className="font-bold text-red-700 w-10 text-right">{w.score}%</span>
                <ActionBadge action={
                  w.score < 40 ? 'Revise Now' : 'Practice More'
                } />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Untested topics */}
      {data.untested_topics.length > 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">
            Untested Topics ({data.untested_topics.length})
          </h2>
          <div className="flex flex-wrap gap-2">
            {data.untested_topics.map(u => (
              <span key={u.topic_key} className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-500 border border-gray-200">
                {u.topic_title}
                {u.attempts > 0 && <span className="ml-1 text-gray-400">({u.attempts} attempt{u.attempts !== 1 ? 's' : ''})</span>}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Chapter accordion */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">All Topics by Chapter</h2>
      {CHAPTER_ORDER.map(chapterId => {
        const topics = byChapter[chapterId]
        return topics ? (
          <ChapterAccordion key={chapterId} chapterId={chapterId} topics={topics} />
        ) : null
      })}
    </div>
  )
}
