import { useEffect, useState } from 'react'
import { getStudyGuidance } from '../../api/client'
import type { GuidanceData } from '../../types'

const SESSION_LABEL: Record<string, string> = {
  understanding:   'Understanding',
  chapter_short:   'Short Test',
  chapter_regular: 'Regular Test',
  mock:            'Mock Test',
}

const SESSION_COLOR: Record<string, string> = {
  understanding:   'bg-blue-100 text-blue-700',
  chapter_short:   'bg-amber-100 text-amber-700',
  chapter_regular: 'bg-orange-100 text-orange-700',
  mock:            'bg-purple-100 text-purple-700',
}

export default function StudyGuidance() {
  const [data, setData]       = useState<GuidanceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  function load(refresh = false) {
    setLoading(true)
    setError('')
    getStudyGuidance(refresh)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(false) }, [])

  return (
    <div className="max-w-3xl mx-auto pb-16">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Study Guidance</h1>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="text-sm text-blue-600 border border-blue-200 rounded-lg px-4 py-1.5 hover:bg-blue-50 disabled:opacity-50 transition"
        >
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {loading && (
        <div className="text-center py-16">
          <div className="text-gray-400 text-sm mb-2">Generating personalised guidance…</div>
          <div className="text-gray-300 text-xs">This may take a few seconds if the AI needs to be called.</div>
        </div>
      )}

      {error && <div className="text-red-500 text-sm mt-4">{error}</div>}

      {data && !loading && (
        <>
          {/* Cache freshness note */}
          {data.cached_at && (
            <p className="text-xs text-gray-400 mb-6">
              Generated: {new Date(data.cached_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
              {' · '}Cached for 24 h. Click Refresh to regenerate.
            </p>
          )}

          {/* Priority Topics */}
          <section className="mb-8">
            <h2 className="text-base font-semibold text-gray-700 mb-4">Priority Topics</h2>
            <div className="space-y-3">
              {(data.priority_topics ?? []).map((t, i) => (
                <div key={i} className="bg-white border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-red-500 font-bold text-sm w-5">{i + 1}</span>
                      <span className="font-semibold text-gray-800">{t.topic_name}</span>
                    </div>
                    <span className="text-sm font-bold text-red-600">{t.current_score}%</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{t.reason}</p>
                  <p className="text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-100">
                    📖 {t.ncert_reference}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* 7-day recommended sequence */}
          <section className="mb-8">
            <h2 className="text-base font-semibold text-gray-700 mb-4">Recommended 7-Day Plan</h2>
            <div className="space-y-2">
              {(data.recommended_sequence ?? []).map(day => (
                <div key={day.day} className="flex items-start gap-3 bg-white border rounded-xl p-3">
                  <div className="shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-500">
                    {day.day}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SESSION_COLOR[day.session_type] ?? 'bg-gray-100 text-gray-600'}`}>
                        {SESSION_LABEL[day.session_type] ?? day.session_type}
                      </span>
                      <span className="text-xs text-gray-400 truncate">{day.focus?.replace(/_/g, ' ') ?? ''}</span>
                    </div>
                    <p className="text-sm text-gray-700">{day.note}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Exam Readiness Projection */}
          {data.exam_readiness_projection && (
            <section>
              <h2 className="text-base font-semibold text-gray-700 mb-4">Exam Readiness Projection</h2>
              <div className="bg-white border rounded-xl p-5">
                <div className="grid grid-cols-3 gap-4 mb-4 text-center">
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Current Estimate</p>
                    <p className="text-2xl font-bold text-gray-800">
                      {data.exam_readiness_projection.current_score}
                      <span className="text-sm font-normal text-gray-400">/30</span>
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Target Score</p>
                    <p className="text-2xl font-bold text-green-700">
                      {data.exam_readiness_projection.target_score}
                      <span className="text-sm font-normal text-gray-400">/30</span>
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Recoverable</p>
                    <p className="text-2xl font-bold text-blue-700">
                      +{data.exam_readiness_projection.marks_recoverable}
                    </p>
                  </div>
                </div>
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
                  {data.exam_readiness_projection.what_if}
                </p>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
