import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { startSpark, completeSpark } from '../api/client'

interface SparkQuestion {
  type: string
  question: string
  options: string[]
  correct_index: number
  hint: string
  solution_approach: string
  explanation: string
}

type AnswerState = 'unanswered' | 'correct' | 'wrong'

const CHAPTER_LABELS: Record<string, string> = {
  ch01_chemical_reactions:   'Chemical Reactions',
  ch02_acids_bases_salts:    'Acids, Bases & Salts',
  ch03_metals_non_metals:    'Metals & Non-Metals',
  ch04_carbon_compounds:     'Carbon Compounds',
  ch05_life_processes:       'Life Processes',
  ch06_control_coordination: 'Control & Coordination',
  ch07_reproduction:         'Reproduction',
  ch08_heredity:             'Heredity & Evolution',
  ch10_light:                'Light',
  ch11_human_eye:            'The Human Eye',
  ch12_electricity:          'Electricity',
  ch13_magnetic_effects:     'Magnetic Effects',
  ch15_our_environment:      'Our Environment',
}

export default function SparkSession() {
  const navigate = useNavigate()

  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [sessionId,  setSessionId]  = useState('')
  const [chapter,    setChapter]    = useState('')
  const [topic,      setTopic]      = useState('')
  const [questions,  setQuestions]  = useState<SparkQuestion[]>([])
  const [current,    setCurrent]    = useState(0)
  const [selected,   setSelected]   = useState<number | null>(null)
  const [state,      setState]      = useState<AnswerState>('unanswered')
  const [correct,    setCorrect]    = useState(0)
  const [done,       setDone]       = useState(false)
  const [result,     setResult]     = useState<{ xp_gained: number; current_streak: number } | null>(null)
  const [finishing,  setFinishing]  = useState(false)
  const [hintShown,  setHintShown]  = useState(false)

  useEffect(() => {
    startSpark()
      .then(data => {
        setSessionId(data.session_id)
        setChapter(data.chapter)
        setTopic(data.topic)
        setQuestions(data.questions)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function handleSelect(idx: number) {
    if (state !== 'unanswered') return
    setSelected(idx)
    const q = questions[current]
    const isCorrect = idx === q.correct_index
    setState(isCorrect ? 'correct' : 'wrong')
    if (isCorrect) setCorrect(c => c + 1)
  }

  function handleNext() {
    if (current + 1 >= questions.length) {
      handleFinish()
    } else {
      setCurrent(c => c + 1)
      setSelected(null)
      setState('unanswered')
      setHintShown(false)
    }
  }

  function handleFinish() {
    setFinishing(true)
    completeSpark(sessionId, correct + (state === 'correct' ? 1 : 0))
      .then(r => {
        setResult(r)
        setDone(true)
      })
      .catch(() => {
        setDone(true)
      })
      .finally(() => setFinishing(false))
  }

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="max-w-xl mx-auto mt-20 text-center">
        <div className="text-4xl mb-4">⚡</div>
        <p className="text-gray-500 text-sm">Generating your Daily Spark…</p>
        <p className="text-gray-400 text-xs mt-1">Picking the right topic for today</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-20 text-center">
        <p className="text-red-500 text-sm mb-4">{error}</p>
        <button onClick={() => navigate('/')} className="text-blue-600 text-sm underline">
          Back to dashboard
        </button>
      </div>
    )
  }

  // ── Completion screen ──────────────────────────────────────────────────────
  if (done) {
    const totalQ = questions.length
    const pct    = Math.round((correct / totalQ) * 100)
    return (
      <div className="max-w-xl mx-auto mt-12">
        <div className="bg-white rounded-2xl border p-8 text-center shadow-sm">
          <div className="text-5xl mb-3">
            {pct >= 80 ? '🔥' : pct >= 50 ? '👍' : '💪'}
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-1">Spark done!</h1>
          <p className="text-gray-500 text-sm mb-6">
            {CHAPTER_LABELS[chapter] ?? chapter} · {topic.replace(/_/g, ' ')}
          </p>

          <div className="flex justify-center gap-8 mb-6">
            <div>
              <p className="text-3xl font-bold text-gray-800">{correct}/{totalQ}</p>
              <p className="text-xs text-gray-400 mt-0.5">Correct</p>
            </div>
            {result && result.xp_gained > 0 && (
              <div>
                <p className="text-3xl font-bold text-blue-600">+{result.xp_gained}</p>
                <p className="text-xs text-gray-400 mt-0.5">XP earned</p>
              </div>
            )}
            {result && (
              <div>
                <p className="text-3xl font-bold text-orange-500">
                  {result.current_streak}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">Day streak</p>
              </div>
            )}
          </div>

          {result && result.current_streak > 0 && (
            <p className="text-sm text-orange-600 font-medium mb-6">
              🔥 {result.current_streak} day streak — keep it going!
            </p>
          )}

          <button
            onClick={() => navigate('/')}
            className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  // ── Question screen ────────────────────────────────────────────────────────
  const q           = questions[current]
  const answered    = state !== 'unanswered'
  const isLastQ     = current + 1 >= questions.length
  const progressPct = Math.round(((current) / questions.length) * 100)

  return (
    <div className="max-w-xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
            ⚡ Daily Spark
          </span>
          <p className="text-xs text-gray-400 mt-1">
            {CHAPTER_LABELS[chapter] ?? chapter} · {topic.replace(/_/g, ' ')}
          </p>
        </div>
        <span className="text-sm font-semibold text-gray-500">
          {current + 1} / {questions.length}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-gray-200 rounded-full mb-6 overflow-hidden">
        <div
          className="h-full bg-amber-400 rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Question card */}
      <div className="bg-white rounded-2xl border shadow-sm p-6 mb-4">
        <p className="text-base font-medium text-gray-800 leading-relaxed mb-6">
          {q.question}
        </p>

        {/* Options */}
        <div className="space-y-3">
          {q.options.map((opt, idx) => {
            const isSelected = selected === idx
            const isCorrectOpt = idx === q.correct_index

            let cls = 'w-full text-left px-4 py-3 rounded-xl border-2 text-sm font-medium transition-all '

            if (!answered) {
              cls += 'border-gray-200 text-gray-700 hover:border-amber-400 hover:bg-amber-50 cursor-pointer'
            } else if (isCorrectOpt) {
              cls += 'border-green-500 bg-green-50 text-green-800'
            } else if (isSelected && !isCorrectOpt) {
              cls += 'border-red-400 bg-red-50 text-red-700'
            } else {
              cls += 'border-gray-200 text-gray-400 cursor-default'
            }

            return (
              <button key={idx} className={cls} onClick={() => handleSelect(idx)} disabled={answered}>
                <span className="inline-block w-6 text-gray-400 font-normal">
                  {['A', 'B', 'C', 'D'][idx]}.
                </span>
                {opt}
                {answered && isCorrectOpt && (
                  <span className="ml-2 text-green-600">✓</span>
                )}
                {answered && isSelected && !isCorrectOpt && (
                  <span className="ml-2 text-red-500">✗</span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Hint (shown before answering, only if question has one) */}
      {!answered && q.hint && (
        <div className="mb-4">
          {hintShown ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <span className="font-semibold">Hint: </span>{q.hint}
            </div>
          ) : (
            <button
              onClick={() => setHintShown(true)}
              className="text-xs text-gray-400 hover:text-amber-600 transition-colors underline underline-offset-2"
            >
              Need a hint?
            </button>
          )}
        </div>
      )}

      {/* Post-answer feedback */}
      {answered && (
        <div className="space-y-3 mb-4">
          {/* Correct / wrong label */}
          <div className={`rounded-xl border px-4 py-2 text-sm font-semibold ${state === 'correct' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'}`}>
            {state === 'correct' ? '✓ Correct!' : '✗ Not quite.'}
          </div>

          {/* Solution approach — how to think about it */}
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
            <p className="font-semibold mb-1 text-blue-700">How to think about it</p>
            <p className="leading-relaxed">{q.solution_approach || q.explanation}</p>
          </div>
        </div>
      )}

      {/* Next button */}
      {answered && (
        <button
          onClick={handleNext}
          disabled={finishing}
          className="w-full bg-amber-500 hover:bg-amber-600 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          {finishing ? 'Saving…' : isLastQ ? 'Finish Spark' : 'Next question →'}
        </button>
      )}
    </div>
  )
}
