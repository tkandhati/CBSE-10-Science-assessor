import { useEffect, useState, useRef } from 'react'
import {
  getQBankStats, getReviewQueue, getLiveBank,
  approveQuestion, rejectQuestion, editQuestion, scanPDF, retagQuestions, getCoverage,
} from '../../api/client'
import type { ReviewQueueQuestion, LiveQuestion, QBankStats, CoverageGap } from '../../types'

type Tab = 'review' | 'live' | 'upload' | 'retag'

const CHAPTERS = [
  { id: 'light', label: 'Light' },
  { id: 'human_eye', label: 'Human Eye' },
  { id: 'electricity', label: 'Electricity' },
  { id: 'magnetic_effects', label: 'Magnetic Effects' },
  { id: 'sources_of_energy', label: 'Sources of Energy' },
]

const TYPES = ['mcq', 'short', 'numerical', 'long', 'assertion_reason', 'case_based']

const DIFF_LABELS: Record<string, string> = {
  '1': 'L1 Remember', '2': 'L2 Understand', '3': 'L3 Apply',
  '4': 'L4 Analyse', '5': 'L5 Evaluate',
}

function DiffPill({ d }: { d: number }) {
  const colors: Record<number, string> = {
    1: 'bg-green-100 text-green-700', 2: 'bg-blue-100 text-blue-700',
    3: 'bg-amber-100 text-amber-700', 4: 'bg-orange-100 text-orange-700',
    5: 'bg-red-100 text-red-700',
  }
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[d] ?? 'bg-gray-100 text-gray-600'}`}>L{d}</span>
}

// ── Stats Panel ──────────────────────────────────────────────────────────────
function StatsPanel({ stats, gaps }: { stats: QBankStats | null; gaps: CoverageGap[] }) {
  if (!stats) return null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <div className="bg-white rounded-xl border p-4 text-center">
        <p className="text-2xl font-bold text-gray-800">{stats.total}</p>
        <p className="text-xs text-gray-400 mt-0.5">Total Questions</p>
      </div>
      <div className="bg-white rounded-xl border p-4 text-center">
        <p className="text-2xl font-bold text-green-700">{stats.approved}</p>
        <p className="text-xs text-gray-400 mt-0.5">Approved</p>
      </div>
      <div className="bg-white rounded-xl border p-4 text-center">
        <p className="text-2xl font-bold text-amber-600">{stats.pending_review}</p>
        <p className="text-xs text-gray-400 mt-0.5">Pending Review</p>
      </div>
      <div className="bg-white rounded-xl border p-4 text-center">
        <p className="text-2xl font-bold text-red-600">{gaps.length}</p>
        <p className="text-xs text-gray-400 mt-0.5">Coverage Gaps</p>
      </div>
    </div>
  )
}

// ── Review Queue ─────────────────────────────────────────────────────────────
function ReviewQueueTab() {
  const [questions, setQuestions] = useState<ReviewQueueQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<ReviewQueueQuestion | null>(null)
  const [editForm, setEditForm] = useState<Partial<ReviewQueueQuestion>>({})
  const [rejectConfirm, setRejectConfirm] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  function load() {
    setLoading(true)
    getReviewQueue({ limit: 30 })
      .then(d => { setQuestions(d.questions); setTotal(d.total) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleApprove(id: string) {
    setSaving(id)
    try {
      await approveQuestion(id)
      setQuestions(q => q.filter(x => x.id !== id))
      setTotal(t => t - 1)
    } catch (e: any) { alert(e.message) }
    finally { setSaving(null) }
  }

  async function handleReject(id: string) {
    setSaving(id)
    try {
      await rejectQuestion(id)
      setQuestions(q => q.filter(x => x.id !== id))
      setTotal(t => t - 1)
      setRejectConfirm(null)
    } catch (e: any) { alert(e.message) }
    finally { setSaving(null) }
  }

  async function handleSaveEdit() {
    if (!editing) return
    setSaving(editing.id)
    try {
      await editQuestion(editing.id, {
        text: editForm.text,
        topic: editForm.topic,
        type: editForm.type,
        difficulty: Number(editForm.difficulty),
        marks: Number(editForm.marks),
        tags: editForm.tags,
      })
      setQuestions(q => q.map(x => x.id === editing.id ? { ...x, ...editForm } : x))
      setEditing(null)
    } catch (e: any) { alert(e.message) }
    finally { setSaving(null) }
  }

  if (loading) return <div className="text-gray-400 text-sm py-8 text-center">Loading review queue…</div>
  if (error) return <div className="text-red-500 text-sm py-8 text-center">{error}</div>
  if (questions.length === 0) return (
    <div className="text-center py-12">
      <p className="text-gray-400 text-sm">Review queue is empty — all questions have been processed.</p>
      <p className="text-gray-300 text-xs mt-1">Upload a PDF to extract new questions.</p>
    </div>
  )

  return (
    <div>
      <p className="text-sm text-gray-500 mb-4">{total} question{total !== 1 ? 's' : ''} pending review</p>
      <div className="space-y-3">
        {questions.map(q => (
          <div key={q.id} className="bg-white border rounded-xl p-4">
            {editing?.id === q.id ? (
              /* Edit form */
              <div className="space-y-3">
                <textarea
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3} value={editForm.text ?? q.text}
                  onChange={e => setEditForm(f => ({ ...f, text: e.target.value }))}
                />
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                  <select className="border rounded px-2 py-1" value={editForm.type ?? q.type}
                    onChange={e => setEditForm(f => ({ ...f, type: e.target.value }))}>
                    {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <select className="border rounded px-2 py-1" value={editForm.difficulty ?? q.difficulty}
                    onChange={e => setEditForm(f => ({ ...f, difficulty: Number(e.target.value) }))}>
                    {[1,2,3,4,5].map(d => <option key={d} value={d}>L{d}</option>)}
                  </select>
                  <input type="number" className="border rounded px-2 py-1" placeholder="Marks"
                    value={editForm.marks ?? q.marks}
                    onChange={e => setEditForm(f => ({ ...f, marks: Number(e.target.value) }))} />
                  <input type="text" className="border rounded px-2 py-1" placeholder="Tags"
                    value={editForm.tags ?? q.tags}
                    onChange={e => setEditForm(f => ({ ...f, tags: e.target.value }))} />
                </div>
                <div className="flex gap-2">
                  <button onClick={handleSaveEdit} disabled={saving === q.id}
                    className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50">
                    {saving === q.id ? 'Saving…' : 'Save changes'}
                  </button>
                  <button onClick={() => setEditing(null)} className="text-xs text-gray-500 underline">Cancel</button>
                </div>
              </div>
            ) : (
              /* View mode */
              <>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-sm text-gray-800 flex-1">{q.text}</p>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <DiffPill d={q.difficulty} />
                    <span className="text-xs text-gray-400">{q.marks}m</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-400 mb-3 flex-wrap">
                  <span className="bg-gray-100 px-2 py-0.5 rounded">{q.chapter}</span>
                  <span className="bg-gray-100 px-2 py-0.5 rounded">{q.topic}</span>
                  <span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded">{q.type}</span>
                  {q.board_years && <span>{q.board_years}</span>}
                </div>
                {rejectConfirm === q.id ? (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-red-600">Confirm reject?</span>
                    <button onClick={() => handleReject(q.id)} disabled={saving === q.id}
                      className="text-xs bg-red-600 text-white px-3 py-1 rounded disabled:opacity-50">
                      Yes, reject
                    </button>
                    <button onClick={() => setRejectConfirm(null)} className="text-xs text-gray-500 underline">Cancel</button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button onClick={() => handleApprove(q.id)} disabled={saving === q.id}
                      className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-50">
                      {saving === q.id ? '…' : '✓ Approve'}
                    </button>
                    <button onClick={() => { setEditing(q); setEditForm({ text: q.text, type: q.type, difficulty: q.difficulty, marks: q.marks, tags: q.tags }) }}
                      className="text-xs border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50">
                      ✏ Edit
                    </button>
                    <button onClick={() => setRejectConfirm(q.id)}
                      className="text-xs border border-red-200 text-red-600 px-3 py-1.5 rounded-lg hover:bg-red-50">
                      ✗ Reject
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Live Bank ────────────────────────────────────────────────────────────────
function LiveBankTab() {
  const [questions, setQuestions] = useState<LiveQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [chapter, setChapter]  = useState('')
  const [type, setType]        = useState('')
  const [search, setSearch]    = useState('')
  const [page, setPage]        = useState(1)

  function load(p = 1) {
    setLoading(true)
    getLiveBank({ chapter: chapter || undefined, type: type || undefined, search: search || undefined, page: p, limit: 20 })
      .then(d => { setQuestions(d.questions); setTotal(d.total); setPage(p) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(1) }, [chapter, type, search])

  return (
    <div>
      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <select className="border rounded-lg px-3 py-1.5 text-sm focus:outline-none"
          value={chapter} onChange={e => setChapter(e.target.value)}>
          <option value="">All chapters</option>
          {CHAPTERS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <select className="border rounded-lg px-3 py-1.5 text-sm focus:outline-none"
          value={type} onChange={e => setType(e.target.value)}>
          <option value="">All types</option>
          {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input type="text" placeholder="Search text…"
          className="border rounded-lg px-3 py-1.5 text-sm flex-1 min-w-[160px] focus:outline-none"
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {loading && <div className="text-gray-400 text-sm text-center py-8">Loading…</div>}
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {!loading && questions.length === 0 && (
        <div className="text-center py-12 text-gray-400 text-sm">
          No questions found{chapter || type || search ? ' for the selected filters' : ''}.
        </div>
      )}

      {!loading && questions.length > 0 && (
        <>
          <p className="text-xs text-gray-400 mb-3">{total} questions</p>
          <div className="bg-white rounded-xl border overflow-hidden">
            {questions.map((q, i) => (
              <div key={q.id} className="border-b last:border-0">
                <button
                  onClick={() => setExpanded(expanded === q.id ? null : q.id)}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 text-left text-sm"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-700 truncate">{q.text_preview}</p>
                    <div className="flex gap-2 mt-1">
                      <span className="text-xs text-gray-400">{q.chapter}</span>
                      <span className="text-xs text-blue-600">{q.type}</span>
                      <DiffPill d={q.difficulty} />
                      <span className="text-xs text-gray-400">{q.marks}m</span>
                      {q.times_served > 0 && <span className="text-xs text-gray-300">×{q.times_served}</span>}
                    </div>
                  </div>
                  <span className="text-gray-400 text-xs shrink-0">{expanded === q.id ? '▲' : '▼'}</span>
                </button>
                {expanded === q.id && (
                  <div className="px-4 pb-4 border-t bg-gray-50 text-sm space-y-2">
                    <p className="text-gray-800 whitespace-pre-wrap">{q.full_text}</p>
                    {q.options && (
                      <div className="space-y-1">
                        {q.options.map((o, j) => (
                          <p key={j} className={`text-xs px-2 py-1 rounded ${o.is_correct ? 'bg-green-100 text-green-700 font-medium' : 'text-gray-600'}`}>
                            {String.fromCharCode(65 + j)}. {o.text}
                          </p>
                        ))}
                      </div>
                    )}
                    {q.expected_answer && (
                      <div className="bg-blue-50 rounded-lg p-2 text-xs text-blue-800">
                        <span className="font-medium">Model: </span>{q.expected_answer}
                      </div>
                    )}
                    {q.key_points?.length > 0 && (
                      <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                        {q.key_points.map((kp, j) => <li key={j}>{kp}</li>)}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* Pagination */}
          {total > 20 && (
            <div className="flex justify-center gap-2 mt-4">
              <button onClick={() => load(page - 1)} disabled={page === 1}
                className="text-sm text-blue-600 px-3 py-1 border rounded disabled:opacity-30">← Prev</button>
              <span className="text-sm text-gray-500 py-1">Page {page}</span>
              <button onClick={() => load(page + 1)} disabled={page * 20 >= total}
                className="text-sm text-blue-600 px-3 py-1 border rounded disabled:opacity-30">Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── PDF Upload Panel ──────────────────────────────────────────────────────────
function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<{ queued: number } | null>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.endsWith('.pdf')) { setError('Please upload a PDF file.'); return }
    setUploading(true)
    setError('')
    setResult(null)
    try {
      const r = await scanPDF(file)
      setResult({ queued: r.queued })
      if (r.queued > 0) onUploaded()
    } catch (e: any) { setError(e.message) }
    finally { setUploading(false) }
  }

  return (
    <div>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
          ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400 bg-gray-50'}`}
      >
        <input ref={fileRef} type="file" accept=".pdf" className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
        {uploading ? (
          <div>
            <div className="text-gray-400 text-sm mb-2">Processing PDF…</div>
            <div className="text-gray-300 text-xs">AI is extracting and tagging questions</div>
          </div>
        ) : (
          <div>
            <p className="text-4xl mb-3">📄</p>
            <p className="text-gray-600 font-medium">Drop a CBSE paper PDF here</p>
            <p className="text-gray-400 text-sm mt-1">or click to browse</p>
          </div>
        )}
      </div>
      {error && <p className="text-red-500 text-sm mt-3">{error}</p>}
      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-xl text-sm text-green-800">
          <p className="font-semibold mb-1">✓ PDF processed</p>
          <p>{result.queued} question{result.queued !== 1 ? 's' : ''} added to the review queue.</p>
          <p className="text-xs text-green-600 mt-1">Switch to the Review Queue tab to approve them.</p>
        </div>
      )}
    </div>
  )
}

// ── Retag Panel ──────────────────────────────────────────────────────────────
function RetagPanel() {
  const [chapter, setChapter] = useState('')
  const [topic, setTopic]     = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult]   = useState<string | null>(null)
  const [error, setError]     = useState('')

  async function handleRetag() {
    setRunning(true); setError(''); setResult(null)
    try {
      const r = await retagQuestions(chapter || undefined, topic || undefined)
      setResult(`${r.retagged} questions retagged.`)
    } catch (e: any) { setError(e.message) }
    finally { setRunning(false) }
  }

  return (
    <div className="max-w-md">
      <p className="text-sm text-gray-600 mb-4">
        Re-run AI classification on pending questions. Useful after correcting a chapter or topic mismatch.
      </p>
      <div className="flex gap-2 mb-4 flex-wrap">
        <select className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[140px]"
          value={chapter} onChange={e => setChapter(e.target.value)}>
          <option value="">All chapters</option>
          {CHAPTERS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
        <input type="text" placeholder="Topic (optional)"
          className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[140px]"
          value={topic} onChange={e => setTopic(e.target.value)} />
      </div>
      <button onClick={handleRetag} disabled={running}
        className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
        {running ? 'Retagging…' : 'Run Retag'}
      </button>
      {error && <p className="text-red-500 text-sm mt-3">{error}</p>}
      {result && <p className="text-green-700 text-sm mt-3 bg-green-50 px-3 py-2 rounded-lg">✓ {result}</p>}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function QuestionBank() {
  const [tab, setTab] = useState<Tab>('review')
  const [stats, setStats] = useState<QBankStats | null>(null)
  const [gaps, setGaps] = useState<CoverageGap[]>([])
  const [reviewKey, setReviewKey] = useState(0)

  useEffect(() => {
    getQBankStats().then(setStats).catch(() => {})
    getCoverage().then(d => setGaps(d.gaps ?? [])).catch(() => {})
  }, [reviewKey])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'review', label: `Review Queue${stats?.pending_review ? ` (${stats.pending_review})` : ''}` },
    { id: 'live',   label: `Live Bank${stats?.approved ? ` (${stats.approved})` : ''}` },
    { id: 'upload', label: 'Upload PDF' },
    { id: 'retag',  label: 'Retag' },
  ]

  return (
    <div className="max-w-5xl mx-auto pb-16">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Question Bank</h1>

      <StatsPanel stats={stats} gaps={gaps} />

      {/* Coverage summary */}
      {gaps.length > 0 && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
          <p className="font-semibold mb-2">Coverage Gaps ({gaps.length})</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {gaps.map((g, i) => (
              <p key={i} className="text-xs">
                <span className="font-medium">{g.chapter}</span> / {g.type} ({g.template}):
                {' '}need {g.needed}, have {g.available} — <span className="text-red-600">gap: {g.gap}</span>
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex border-b mb-6 gap-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors
              ${tab === t.id ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'review' && <ReviewQueueTab key={reviewKey} />}
      {tab === 'live'   && <LiveBankTab />}
      {tab === 'upload' && <UploadPanel onUploaded={() => setReviewKey(k => k + 1)} />}
      {tab === 'retag'  && <RetagPanel />}
    </div>
  )
}
