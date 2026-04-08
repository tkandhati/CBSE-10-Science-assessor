import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { getSessionQuestions, submitSession, markDoneWriting } from '../api/client'
import type { Question, SessionResponse, AnswerSubmission } from '../types'

// ── Mock Test: sectioned read-only paper view ─────────────────────────────────

const SECTION_INSTRUCTIONS: Record<string, string> = {
  A: 'Section A — Answer all questions. Each question carries 1 mark. (MCQ / Assertion-Reason)',
  B: 'Section B — Short Answer I. Each question carries 2 marks.',
  C: 'Section C — Short Answer II. Each question carries 3 marks.',
  D: 'Section D — Long Answer. Each question carries 5 marks.',
  E: 'Section E — Case-Based Questions. Each question carries 4 marks.',
}

function MockTestView({ session }: { session: SessionResponse }) {
  const navigate = useNavigate()
  const [marking, setMarking] = useState(false)
  const [error,   setError]   = useState('')

  async function handleDoneWriting() {
    setMarking(true)
    setError('')
    try {
      await markDoneWriting(session.session_id)
      navigate(`/session/${session.session_id}/upload`, { state: { session } })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update status.')
      setMarking(false)
    }
  }

  const typeLabel: Record<string, string> = {
    mcq: 'MCQ', short: 'Short Answer', numerical: 'Numerical',
    long: 'Long Answer', diagram: 'Diagram', assertion_reason: 'Assertion & Reason',
    case_based: 'Case Based',
  }

  // Group questions by section in order A→B→C→D→E
  const sectionOrder = ['A', 'B', 'C', 'D', 'E']
  const grouped: Record<string, typeof session.questions> = {}
  for (const q of session.questions) {
    const sec = q.section ?? 'A'
    if (!grouped[sec]) grouped[sec] = []
    grouped[sec].push(q)
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-28">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <h1 className="text-lg font-bold text-gray-800">Full Mock Test</h1>
        <p className="text-sm text-gray-500">
          All 5 Physics Chapters · {session.total_questions} questions · {session.total_marks} marks
        </p>
        <div className="flex items-center gap-4 mt-2">
          <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-purple-700 bg-purple-50 px-3 py-1 rounded-full border border-purple-200">
            ⏱ Duration: 3 Hours
          </span>
          <span className="text-xs text-amber-600 font-medium">
            Write answers on paper — upload PDF when done
          </span>
        </div>
      </div>

      {/* Sectioned questions */}
      <div className="max-w-3xl mx-auto p-6 space-y-8">
        {sectionOrder.map(sec => {
          const qs = grouped[sec]
          if (!qs || qs.length === 0) return null
          const sectionMarks = qs.reduce((sum, q) => sum + q.marks, 0)
          return (
            <div key={sec}>
              {/* Section header */}
              <div className="bg-indigo-600 text-white rounded-xl px-5 py-3 mb-4">
                <p className="font-bold text-base">Section {sec}</p>
                <p className="text-xs opacity-80 mt-0.5">{SECTION_INSTRUCTIONS[sec]}</p>
                <p className="text-xs opacity-80">{qs.length} question{qs.length !== 1 ? 's' : ''} · {sectionMarks} marks</p>
              </div>

              <div className="space-y-4">
                {qs.map((q) => (
                  <div key={q.id} className="bg-white rounded-xl border shadow-sm p-5">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold uppercase text-gray-400">
                        Q{q.sequence} · {typeLabel[q.type] ?? q.type} · {q.marks} mark{q.marks !== 1 ? 's' : ''}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                        ${q.difficulty <= 1 ? 'bg-green-100 text-green-700' :
                          q.difficulty <= 2 ? 'bg-blue-100 text-blue-700' :
                          q.difficulty <= 3 ? 'bg-amber-100 text-amber-700' :
                                              'bg-red-100 text-red-700'}`}>
                        L{q.difficulty}
                      </span>
                    </div>

                    {q.type === 'numerical' && q.generated_params && (
                      <div className="bg-blue-50 rounded-lg p-3 mb-3 text-sm text-blue-800">
                        <strong>Given:</strong>{' '}
                        {Object.entries(q.generated_params.variables)
                          .map(([k, v]) => `${k} = ${v}`)
                          .join(', ')}
                        {q.generated_params.units && (
                          <span className="ml-2 text-gray-500">(answer in {q.generated_params.units})</span>
                        )}
                      </div>
                    )}

                    <p className="text-gray-800 leading-relaxed">{q.text}</p>

                    {q.diagram_path && (
                      <div className="my-4 flex justify-center">
                        <img
                          src={`/diagrams/${q.diagram_path}`}
                          alt="Question diagram"
                          className="max-w-full max-h-96 border border-gray-200 rounded"
                        />
                      </div>
                    )}

                    {(q.type === 'mcq' || q.type === 'assertion_reason') && q.options && (
                      <div className="mt-3 space-y-2">
                        {q.options.map((opt, idx) => (
                          <div key={idx} className="flex gap-2 text-sm text-gray-700">
                            <span className="font-medium text-gray-400 w-5 shrink-0">
                              {String.fromCharCode(65 + idx)}.
                            </span>
                            <span>{opt.text}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Sticky footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t px-6 py-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">Finished writing all answers on paper?</p>
        <div className="flex flex-col items-end gap-1">
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            onClick={handleDoneWriting}
            disabled={marking}
            className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg disabled:opacity-50"
          >
            {marking ? 'Updating…' : 'Done Writing — Upload PDF →'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Chapter Test: read-only paper view ───────────────────────────────────────

function ChapterTestView({ session }: { session: SessionResponse }) {
  const navigate = useNavigate()
  const [marking, setMarking] = useState(false)
  const [error,   setError]   = useState('')

  async function handleDoneWriting() {
    setMarking(true)
    setError('')
    try {
      await markDoneWriting(session.session_id)
      navigate(`/session/${session.session_id}/upload`, { state: { session } })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update status.')
      setMarking(false)
    }
  }

  const typeLabel: Record<string, string> = {
    mcq: 'MCQ', short: 'Short Answer', numerical: 'Numerical',
    long: 'Long Answer', diagram: 'Diagram', assertion_reason: 'Assertion & Reason',
    case_based: 'Case Based',
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <h1 className="text-lg font-bold text-gray-800">{session.chapter}</h1>
        <p className="text-sm text-gray-500">
          {session.type === 'chapter_short' ? 'Short Chapter Test' : 'Regular Chapter Test'}
          {' · '}{session.total_questions} questions · {session.total_marks} marks
        </p>
        <p className="text-xs text-amber-600 mt-1 font-medium">
          Write your answers on paper. When finished, click the button below.
        </p>
      </div>

      {/* Question list — read-only */}
      <div className="max-w-3xl mx-auto p-6 space-y-5">
        {session.questions.map((q) => (
          <div key={q.id} className="bg-white rounded-xl border shadow-sm p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase text-gray-400">
                Q{q.sequence} · {typeLabel[q.type] ?? q.type} · {q.marks} mark{q.marks !== 1 ? 's' : ''}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                ${q.difficulty <= 1 ? 'bg-green-100 text-green-700' :
                  q.difficulty <= 2 ? 'bg-blue-100 text-blue-700' :
                  q.difficulty <= 3 ? 'bg-amber-100 text-amber-700' :
                                      'bg-red-100 text-red-700'}`}>
                L{q.difficulty}
              </span>
            </div>

            {/* For numerical: show given variables */}
            {q.type === 'numerical' && q.generated_params && (
              <div className="bg-blue-50 rounded-lg p-3 mb-3 text-sm text-blue-800">
                <strong>Given:</strong>{' '}
                {Object.entries(q.generated_params.variables)
                  .map(([k, v]) => `${k} = ${v}`)
                  .join(', ')}
                {q.generated_params.units && (
                  <span className="ml-2 text-gray-500">(answer in {q.generated_params.units})</span>
                )}
              </div>
            )}

            <p className="text-gray-800 leading-relaxed">{q.text}</p>

            {q.diagram_path && (
              <div className="my-4 flex justify-center">
                <img
                  src={`/diagrams/${q.diagram_path}`}
                  alt="Question diagram"
                  className="max-w-full max-h-96 border border-gray-200 rounded"
                />
              </div>
            )}

            {/* MCQ options shown for reference */}
            {(q.type === 'mcq' || q.type === 'assertion_reason') && q.options && (
              <div className="mt-3 space-y-2">
                {q.options.map((opt, idx) => (
                  <div key={idx} className="flex gap-2 text-sm text-gray-700">
                    <span className="font-medium text-gray-400 w-5 shrink-0">
                      {String.fromCharCode(65 + idx)}.
                    </span>
                    <span>{opt.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Sticky footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t px-6 py-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">Finished writing all answers on paper?</p>
        <div className="flex flex-col items-end gap-1">
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            onClick={handleDoneWriting}
            disabled={marking}
            className="px-6 py-2 bg-green-600 text-white font-semibold rounded-lg disabled:opacity-50"
          >
            {marking ? 'Updating…' : 'Done Writing — Upload PDF →'}
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Understanding Session: interactive answer view ────────────────────────────

interface AnswerState {
  selectedOption?: number
  answerText?: string
  timeSeconds: number
  instantResult?: 'correct' | 'wrong' | null
}

function MCQOptions({
  question, answer, onChange,
}: { question: Question; answer: AnswerState; onChange: (idx: number) => void }) {
  const opts = question.options ?? []
  return (
    <div className="space-y-3 mt-4">
      {opts.map((opt, idx) => {
        let border = 'border-gray-200 hover:border-blue-400'
        let bg = 'bg-white'
        if (answer.selectedOption === idx) {
          if (answer.instantResult === 'correct') { border = 'border-green-500'; bg = 'bg-green-50' }
          else if (answer.instantResult === 'wrong') { border = 'border-red-400'; bg = 'bg-red-50' }
          else { border = 'border-blue-500'; bg = 'bg-blue-50' }
        } else if (answer.instantResult === 'wrong' && idx === question.correct_option_index) {
          border = 'border-green-400'; bg = 'bg-green-50'
        }
        return (
          <button
            key={idx} onClick={() => onChange(idx)}
            disabled={answer.instantResult != null}
            className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-colors ${border} ${bg}`}
          >
            <span className="font-medium text-gray-500 mr-2">{String.fromCharCode(65 + idx)}.</span>
            {opt.text}
          </button>
        )
      })}
    </div>
  )
}

function NumericalInput({ question, answer, onChange, onCheck }: {
  question: Question; answer: AnswerState
  onChange: (v: string) => void; onCheck: () => void
}) {
  const gp = question.generated_params
  const parts = gp?.expected_parts

  // Parse multi-part answers from JSON string
  const partValues: Record<string, string> = (() => {
    if (!parts) return {}
    try { return JSON.parse(answer.answerText ?? '{}') } catch { return {} }
  })()

  const updatePart = (label: string, val: string) => {
    const updated = { ...partValues, [label]: val }
    onChange(JSON.stringify(updated))
  }

  const allPartsFilled = parts ? parts.every(p => (partValues[p.label] ?? '').trim() !== '') : false

  if (parts && parts.length > 1) {
    return (
      <div className="mt-4 space-y-3">
        {gp && Object.keys(gp.variables).length > 0 && (
          <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">
            <strong>Given:</strong>{' '}
            {Object.entries(gp.variables).map(([k, v]) => `${k} = ${v}`).join(', ')}
          </div>
        )}
        <div className="space-y-2">
          {parts.map((part, i) => {
            const letter = String.fromCharCode(97 + i)
            const checked = answer.instantResult != null
            const partCorrect = checked && (() => {
              const sv = parseFloat(partValues[part.label] ?? '')
              const tol = Math.max(Math.pow(10, -(gp?.answer_precision ?? 0)), Math.abs(part.value) * 0.02)
              return !isNaN(sv) && Math.abs(sv - part.value) <= tol
            })()
            return (
              <div key={part.label} className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-600 w-5">({letter})</span>
                <input
                  type="number" step="any"
                  placeholder={`Answer in ${part.units || gp?.units || 'J'}`}
                  value={partValues[part.label] ?? ''}
                  onChange={e => updatePart(part.label, e.target.value)}
                  disabled={checked}
                  className="flex-1 border-2 border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-blue-500 outline-none"
                />
                {checked && (
                  partCorrect
                    ? <span className="text-green-600 text-sm font-medium">✓</span>
                    : <span className="text-red-500 text-sm">{part.value} {part.units}</span>
                )}
              </div>
            )
          })}
        </div>
        {answer.instantResult == null && (
          <button onClick={onCheck} disabled={!allPartsFilled}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-40 text-sm">
            Check All
          </button>
        )}
        {answer.instantResult === 'correct' && <p className="text-green-600 font-medium">All correct!</p>}
        {answer.instantResult === 'wrong' && <p className="text-amber-600 font-medium">Some parts incorrect — see above.</p>}
      </div>
    )
  }

  return (
    <div className="mt-4 space-y-3">
      {gp && (
        <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">
          <strong>Given:</strong>{' '}
          {Object.entries(gp.variables).map(([k, v]) => `${k} = ${v}`).join(', ')}
          {gp.units && <span className="ml-2 text-gray-500">(answer in {gp.units})</span>}
        </div>
      )}
      <div className="flex gap-2">
        <input
          type="number" step="any" placeholder="Enter your answer"
          value={answer.answerText ?? ''}
          onChange={e => onChange(e.target.value)}
          disabled={answer.instantResult != null}
          className="flex-1 border-2 border-gray-200 rounded-lg px-4 py-2 focus:border-blue-500 outline-none"
        />
        {answer.instantResult == null && (
          <button onClick={onCheck} disabled={!answer.answerText}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-40">
            Check
          </button>
        )}
      </div>
      {answer.instantResult === 'correct' && <p className="text-green-600 font-medium">Correct!</p>}
      {answer.instantResult === 'wrong' && (
        <p className="text-red-500 font-medium">
          Incorrect. Answer: {gp?.expected_answer_str ?? gp?.expected_answer}
        </p>
      )}
    </div>
  )
}

function UnderstandingView({ session }: { session: SessionResponse }) {
  const navigate  = useNavigate()
  const [currentIdx, setCurrentIdx] = useState(0)
  const [answers,    setAnswers]    = useState<Record<string, AnswerState>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error,      setError]      = useState('')
  const tickRef = useRef<() => void>(() => {})

  const questions = session.questions
  const q = questions[currentIdx]

  const getAns = (qid: string): AnswerState => answers[qid] ?? { timeSeconds: 0 }
  const updAns = (qid: string, p: Partial<AnswerState>) =>
    setAnswers(prev => ({ ...prev, [qid]: { ...getAns(qid), ...p } }))

  tickRef.current = () => { if (q) updAns(q.id, { timeSeconds: getAns(q.id).timeSeconds + 1 }) }

  useEffect(() => {
    const t = setInterval(() => tickRef.current(), 1000)
    return () => clearInterval(t)
  }, [])

  const handleMCQ = (idx: number) => {
    if (!q) return
    updAns(q.id, { selectedOption: idx, instantResult: q.correct_option_index === idx ? 'correct' : 'wrong' })
  }

  const handleNumCheck = () => {
    if (!q) return
    const parts = q.generated_params?.expected_parts
    if (parts && parts.length > 1) {
      // Multi-part: check each part
      let partValues: Record<string, string> = {}
      try { partValues = JSON.parse(getAns(q.id).answerText ?? '{}') } catch { /* empty */ }
      const precision = q.generated_params?.answer_precision ?? 0
      const allCorrect = parts.every(p => {
        const sv = parseFloat(partValues[p.label] ?? '')
        const tol = Math.max(Math.pow(10, -precision), Math.abs(p.value) * 0.02)
        return !isNaN(sv) && Math.abs(sv - p.value) <= tol
      })
      updAns(q.id, { instantResult: allCorrect ? 'correct' : 'wrong' })
      return
    }
    const val = parseFloat(getAns(q.id).answerText ?? '')
    const exp = q.generated_params?.expected_answer
    if (isNaN(val) || exp == null) return
    const tol = Math.abs(exp) * 0.02 || 0.01
    updAns(q.id, { instantResult: Math.abs(val - exp) <= tol ? 'correct' : 'wrong' })
  }

  async function handleSubmit() {
    setSubmitting(true)
    const subs: AnswerSubmission[] = questions.map(q => ({
      question_id:     q.id,
      answer_text:     getAns(q.id).answerText,
      selected_option: getAns(q.id).selectedOption,
      time_seconds:    getAns(q.id).timeSeconds,
    }))
    try {
      const resp = await submitSession(session.session_id, subs)
      // Pass only celebration data; Results page fetches full breakdown from API
      navigate(`/session/${session.session_id}/results`, {
        state: {
          new_badges:    resp.new_badges    ?? [],
          leveled_up:    resp.leveled_up    ?? false,
          current_level: resp.current_level ?? 1,
        },
      })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submit failed')
      setSubmitting(false)
    }
  }

  const answered = questions.filter(q => {
    const a = getAns(q.id)
    return a.selectedOption != null || (a.answerText ?? '').trim().length > 0
  }).length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <div>
          <span className="font-semibold text-gray-700">{session.chapter}</span>
          {session.topic && <span className="text-gray-400 ml-2">· {session.topic}</span>}
        </div>
        <div className="text-sm text-gray-500">
          {answered}/{questions.length} answered · {session.total_marks} marks
        </div>
      </div>
      <div className="h-1 bg-gray-200">
        <div className="h-1 bg-blue-500 transition-all"
          style={{ width: `${(answered / Math.max(questions.length, 1)) * 100}%` }} />
      </div>

      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Dot nav */}
        <div className="flex flex-wrap gap-2">
          {questions.map((q, idx) => {
            const a   = getAns(q.id)
            const has = a.selectedOption != null || (a.answerText ?? '').trim().length > 0
            const dot = idx === currentIdx ? 'bg-blue-500' : has ? 'bg-green-400' : 'bg-gray-200'
            return (
              <button key={q.id} onClick={() => setCurrentIdx(idx)}
                className={`w-8 h-8 rounded-full text-xs font-bold text-white ${dot}`}>
                {idx + 1}
              </button>
            )
          })}
        </div>

        {q && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <div className="flex items-start justify-between mb-2">
              <span className="text-xs font-semibold uppercase text-gray-400">
                Q{currentIdx + 1} · {q.type.replace('_', ' ')} · {q.marks} mark{q.marks !== 1 ? 's' : ''}
              </span>
              <span className="text-xs text-gray-400">
                {Math.floor(getAns(q.id).timeSeconds / 60)}m {getAns(q.id).timeSeconds % 60}s
              </span>
            </div>
            <p className="text-gray-800 text-lg leading-relaxed">{q.text}</p>
            {q.diagram_path && (
              <div className="my-4 flex justify-center">
                <img
                  src={`/diagrams/${q.diagram_path}`}
                  alt="Question diagram"
                  className="max-w-full max-h-96 border border-gray-200 rounded"
                />
              </div>
            )}
            {q.type === 'mcq' || q.type === 'assertion_reason' ? (
              <MCQOptions question={q} answer={getAns(q.id)} onChange={handleMCQ} />
            ) : q.type === 'numerical' ? (
              <NumericalInput question={q} answer={getAns(q.id)}
                onChange={v => updAns(q.id, { answerText: v })} onCheck={handleNumCheck} />
            ) : (
              <textarea className="mt-4 w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:border-blue-500 outline-none resize-none"
                rows={6} placeholder="Write your answer here…"
                value={getAns(q.id).answerText ?? ''}
                onChange={e => updAns(q.id, { answerText: e.target.value })} />
            )}

            {/* Hint — always visible before answering, like Spark */}
            {(() => {
              const hintText = q.rubric?.hint ?? q.rubric?.key_points?.[0] ?? q.rubric?.keywords?.[0] ?? null
              if (!hintText || getAns(q.id).instantResult != null) return null
              return (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  <span className="font-semibold">Hint: </span>{hintText}
                </div>
              )
            })()}

            {/* Post-answer concept explanation — MCQ and Numerical only */}
            {(q.type === 'mcq' || q.type === 'assertion_reason' || q.type === 'numerical') &&
              getAns(q.id).instantResult != null &&
              (q.rubric?.key_points?.length ?? 0) > 0 && (
                <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
                  <p className="font-semibold mb-2 text-blue-700">How to think about it</p>
                  <ul className="space-y-1 list-disc list-inside leading-relaxed">
                    {q.rubric!.key_points.slice(0, 2).map((kp, i) => (
                      <li key={i}>{kp}</li>
                    ))}
                  </ul>
                </div>
              )
            }
          </div>
        )}

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <div className="flex justify-between">
          <button onClick={() => setCurrentIdx(i => Math.max(i - 1, 0))} disabled={currentIdx === 0}
            className="px-4 py-2 border rounded-lg disabled:opacity-30">Previous</button>
          {currentIdx < questions.length - 1 ? (
            <button onClick={() => setCurrentIdx(i => i + 1)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg">Next</button>
          ) : (
            <button onClick={handleSubmit} disabled={submitting}
              className="px-6 py-2 bg-green-600 text-white rounded-lg font-semibold disabled:opacity-60">
              {submitting ? 'Submitting…' : 'Submit Session'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}


// ── Main component ────────────────────────────────────────────────────────────

export default function TakeSession() {
  const { id }       = useParams<{ id: string }>()
  const location     = useLocation()
  const [session, setSession] = useState<SessionResponse | null>(
    (location.state as { session?: SessionResponse })?.session ?? null
  )
  const [loading, setLoading] = useState(!session)
  const [error,   setError]   = useState('')

  useEffect(() => {
    if (!session && id) {
      getSessionQuestions(id)
        .then(setSession)
        .catch(e => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [id, session])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading session…</div>
  if (error)   return <div className="p-8 text-center text-red-500">{error}</div>
  if (!session) return null

  if (session.type === 'mock') {
    return <MockTestView session={session} />
  }
  if (session.type === 'chapter_short' || session.type === 'chapter_regular') {
    return <ChapterTestView session={session} />
  }
  return <UnderstandingView session={session} />
}
