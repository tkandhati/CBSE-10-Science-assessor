import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createSession, getSyllabus, getActiveSession } from '../api/client'
import type { ChapterInfo } from '../types'

const ALL_CHAPTERS = [
  { id: 'ch01_chemical_reactions',   title: 'Ch 1  — Chemical Reactions & Equations' },
  { id: 'ch02_acids_bases_salts',    title: 'Ch 2  — Acids, Bases and Salts' },
  { id: 'ch03_metals_non_metals',    title: 'Ch 3  — Metals and Non-Metals' },
  { id: 'ch04_carbon_compounds',     title: 'Ch 4  — Carbon and its Compounds' },
  { id: 'ch05_life_processes',       title: 'Ch 6  — Life Processes' },
  { id: 'ch06_control_coordination', title: 'Ch 7  — Control and Coordination' },
  { id: 'ch07_reproduction',         title: 'Ch 8  — How do Organisms Reproduce?' },
  { id: 'ch08_heredity',             title: 'Ch 9  — Heredity and Evolution' },
  { id: 'ch10_light',                title: 'Ch 10 — Light: Reflection & Refraction' },
  { id: 'ch11_human_eye',            title: 'Ch 11 — Human Eye & Colourful World' },
  { id: 'ch12_electricity',          title: 'Ch 12 — Electricity' },
  { id: 'ch13_magnetic_effects',     title: 'Ch 13 — Magnetic Effects of Current' },
  { id: 'ch15_our_environment',      title: 'Ch 15 — Our Environment' },
]

type Mode = 'understanding' | 'chapter_short' | 'chapter_regular' | 'mock'

const MODES: { id: Mode; label: string; sub: string; color: string }[] = [
  {
    id:    'understanding',
    label: 'Understanding Session',
    sub:   '10–12 Q · AI-selected · instant feedback',
    color: 'border-blue-500 bg-blue-50 text-blue-700',
  },
  {
    id:    'chapter_short',
    label: 'Short Chapter Test',
    sub:   '6 Q · 14 marks · 20 min · write on paper',
    color: 'border-amber-500 bg-amber-50 text-amber-700',
  },
  {
    id:    'chapter_regular',
    label: 'Regular Chapter Test',
    sub:   '15 Q · 40 marks · 45 min · write on paper',
    color: 'border-orange-500 bg-orange-50 text-orange-700',
  },
  {
    id:    'mock',
    label: 'Full Mock Test',
    sub:   '39 Q · 80 marks · 3 hours · all 13 Science chapters',
    color: 'border-purple-600 bg-purple-50 text-purple-700',
  },
]

export default function StartSession() {
  const navigate = useNavigate()
  const [mode,    setMode]    = useState<Mode>('understanding')
  const [chapter, setChapter] = useState('')
  const [topic,   setTopic]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [syllabusMap, setSyllabusMap] = useState<Record<string, ChapterInfo>>({})
  const [activeTest,  setActiveTest]  = useState<{ id: string; type: string } | null>(null)
  const [mockConfirm, setMockConfirm] = useState(false)

  useEffect(() => {
    getSyllabus()
      .then(data => {
        const m: Record<string, ChapterInfo> = {}
        for (const ch of data.chapters) m[ch.id] = ch
        setSyllabusMap(m)
      })
      .catch(() => {})

    getActiveSession()
      .then(r => {
        if (
          r.active_session_id &&
          (r.status === 'in_progress' || r.status === 'awaiting_upload') &&
          (r.type === 'chapter_short' || r.type === 'chapter_regular' || r.type === 'mock')
        ) {
          setActiveTest({ id: r.active_session_id, type: r.type ?? '' })
        }
      })
      .catch(() => {})
  }, [])

  const chapterTopics = syllabusMap[chapter]?.topics ?? []
  const isMock        = mode === 'mock'
  const isPaperTest   = mode !== 'understanding'

  function handleModeChange(m: Mode) {
    setMode(m)
    setTopic('')
    setMockConfirm(false)
    setError('')
  }

  function handleChapterChange(id: string) {
    setChapter(id)
    setTopic('')
  }

  async function handleStart() {
    if (!isMock && !chapter) { setError('Please select a chapter.'); return }
    if (isPaperTest && activeTest) {
      setError(`Active test (${activeTest.id}) in progress. Complete it before starting a new one.`)
      return
    }
    if (isMock && !mockConfirm) {
      setMockConfirm(true)
      return
    }
    setLoading(true)
    setError('')
    try {
      const session = await createSession(mode, isMock ? 'all' : chapter, isPaperTest ? undefined : (topic || undefined))
      navigate(`/session/${session.session_id}`, { state: { session } })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to create session.'
      if (msg.includes('FEASIBILITY_FAIL') || msg.includes('gaps')) {
        setError('Not enough approved questions for this paper. Contact admin.')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto mt-10 pb-12">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">New Session</h1>

      {/* Active test warning */}
      {activeTest && (
        <div className="mb-5 p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-sm">
          <p className="font-semibold mb-1">
            {activeTest.type === 'mock' ? 'Mock test' : 'Chapter test'} in progress
          </p>
          <p>
            <button
              onClick={() => navigate(`/session/${activeTest.id}`)}
              className="underline font-medium"
            >
              Resume it
            </button>{' '}before starting a new test.
          </p>
        </div>
      )}

      {/* Mode picker */}
      <div className="grid gap-3 mb-6">
        {MODES.map(m => (
          <button
            key={m.id}
            onClick={() => handleModeChange(m.id)}
            className={`text-left p-4 rounded-xl border-2 transition-all
              ${mode === m.id ? m.color + ' border-2' : 'border-gray-200 bg-white hover:border-gray-300'}`}
          >
            <p className={`font-semibold ${mode === m.id ? '' : 'text-gray-700'}`}>{m.label}</p>
            <p className={`text-xs mt-0.5 ${mode === m.id ? 'opacity-70' : 'text-gray-400'}`}>{m.sub}</p>
          </button>
        ))}
      </div>

      {/* Chapter picker — not shown for mock */}
      {!isMock && (
        <>
          <label className="block text-sm font-medium text-gray-700 mb-1">Chapter</label>
          <select
            className="w-full border rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={chapter}
            onChange={e => handleChapterChange(e.target.value)}
          >
            <option value="">-- Select a chapter --</option>
            {ALL_CHAPTERS.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </>
      )}

      {/* Topic picker — Understanding only */}
      {!isPaperTest && chapter && (
        <>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Topic <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          {chapterTopics.length > 0 ? (
            <select
              className="w-full border rounded-lg px-3 py-2 mb-6 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={topic}
              onChange={e => setTopic(e.target.value)}
            >
              <option value="">-- All topics --</option>
              {chapterTopics.map(t => (
                <option key={t.id} value={t.id}>{t.title}</option>
              ))}
            </select>
          ) : (
            <input
              className="w-full border rounded-lg px-3 py-2 mb-6 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Leave blank for full chapter"
              value={topic}
              onChange={e => setTopic(e.target.value)}
            />
          )}
        </>
      )}

      {/* Mock confirmation card */}
      {isMock && mockConfirm && !activeTest && (
        <div className="mb-6 p-5 rounded-xl border-2 border-purple-300 bg-purple-50">
          <p className="font-bold text-purple-800 mb-3">Full Mock Test — Confirm</p>
          <ul className="text-sm text-purple-700 space-y-1 mb-4">
            <li>• 39 questions · 80 marks · 3 hours</li>
            <li>• All 13 Science chapters (Chemistry Ch1–4, Biology Ch6–9, Physics Ch10–13, Environment Ch15)</li>
            <li>• Write all answers on paper — handwritten answer sheet</li>
            <li>• Upload PDF scan after finishing to get AI scoring</li>
            <li>• Paper is generated fresh from the question bank — zero AI, fully deterministic</li>
          </ul>
          <p className="text-xs text-purple-500">Clicking "Start Mock" below will generate your paper.</p>
        </div>
      )}

      {isMock && !mockConfirm && !activeTest && (
        <div className="mb-6 p-4 rounded-xl border border-gray-200 bg-gray-50 text-sm text-gray-600">
          Full mock covers all 13 Science chapters · 3 hours · handwritten on paper · AI-scored via PDF upload.
        </div>
      )}

      {!isPaperTest && !chapter && <div className="mb-6" />}
      {isPaperTest && !isMock && <div className="mb-6" />}

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      <button
        onClick={handleStart}
        disabled={
          loading ||
          (!isMock && !chapter) ||
          (isPaperTest && !!activeTest)
        }
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-3 rounded-lg transition"
      >
        {loading
          ? 'Generating paper…'
          : isMock && !mockConfirm
            ? 'Review & Start Mock →'
            : isMock
              ? 'Start Mock Test'
              : 'Start Session'}
      </button>

      {isPaperTest && !isMock && (
        <p className="text-xs text-gray-400 mt-3 text-center">
          Paper generated from question bank · Write answers on paper · Upload PDF for AI scoring
        </p>
      )}
    </div>
  )
}
