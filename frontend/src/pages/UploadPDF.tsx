import { useCallback, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { uploadPDF, confirmOCR, submitChapterTest } from '../api/client'
import type { SessionResponse, OCRItem } from '../types'

type Stage = 'upload' | 'confirming' | 'scoring' | 'done'

function ConfidenceBadge({ conf }: { conf: number }) {
  const pct = Math.round(conf * 100)
  const color = conf >= 0.75 ? 'bg-green-100 text-green-700'
    : conf >= 0.5 ? 'bg-amber-100 text-amber-700'
    : 'bg-red-100 text-red-600'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${color}`}>{pct}%</span>
}

export default function UploadPDF() {
  const { id }   = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()

  const session = (location.state as { session?: SessionResponse })?.session ?? null

  const [stage,        setStage]        = useState<Stage>('upload')
  const [file,         setFile]         = useState<File | null>(null)
  const [dragOver,     setDragOver]     = useState(false)
  const [uploading,    setUploading]    = useState(false)
  const [error,        setError]        = useState('')
  const [lowConfItems, setLowConfItems] = useState<OCRItem[]>([])
  const [corrections,  setCorrections]  = useState<Record<string, string>>({})
  const [submitting,   setSubmitting]   = useState(false)

  // ── Drag-and-drop ─────────────────────────────────────────────────────────
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') setFile(dropped)
    else setError('Please drop a PDF file.')
  }, [])

  // ── Upload + OCR ──────────────────────────────────────────────────────────
  async function handleUpload() {
    if (!file || !id) return
    setUploading(true)
    setError('')
    try {
      const result = await uploadPDF(id, file)
      if (result.low_confidence.length > 0) {
        // Initialise corrections with OCR text
        const init: Record<string, string> = {}
        for (const item of result.low_confidence) {
          init[item.question_id] = item.ocr_text
        }
        setCorrections(init)
        setLowConfItems(result.low_confidence)
        setStage('confirming')
      } else {
        // All high-confidence — go straight to scoring
        await runScoring()
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  // ── Confirm OCR + Score ───────────────────────────────────────────────────
  async function handleConfirmAndScore() {
    if (!id) return
    setSubmitting(true)
    setError('')
    try {
      // Save confirmed/corrected answers
      const confirmations = Object.entries(corrections).map(([question_id, answer_text]) => ({
        question_id,
        answer_text,
      }))
      await confirmOCR(id, confirmations)
      await runScoring()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to confirm.')
      setSubmitting(false)
    }
  }

  async function runScoring() {
    if (!id) return
    setStage('scoring')
    try {
      const results = await submitChapterTest(id)
      navigate(`/session/${id}/results`, { state: { results } })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Scoring failed.')
      setStage('confirming')
    }
  }

  // ── Upload stage ──────────────────────────────────────────────────────────
  if (stage === 'upload') {
    return (
      <div className="max-w-lg mx-auto mt-10">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Upload Answer Sheet</h1>
          {session && (
            <p className="text-sm text-gray-500 mt-1">
              {session.chapter} ·{' '}
              {session.type === 'chapter_short' ? 'Short Chapter Test' : 'Regular Chapter Test'}
            </p>
          )}
        </div>

        {/* Drop zone */}
        <div
          onDrop={onDrop}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => document.getElementById('pdf-input')?.click()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
            ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'}`}
        >
          <div className="text-4xl mb-3">📄</div>
          {file ? (
            <div>
              <p className="font-semibold text-gray-700">{file.name}</p>
              <p className="text-sm text-gray-400 mt-1">{(file.size / 1024).toFixed(0)} KB</p>
            </div>
          ) : (
            <div>
              <p className="font-medium text-gray-600">Drag & drop your answer sheet PDF</p>
              <p className="text-sm text-gray-400 mt-1">or click to browse</p>
            </div>
          )}
          <input
            id="pdf-input" type="file" accept="application/pdf" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f) }}
          />
        </div>

        {file && (
          <p className="text-xs text-gray-400 mt-2 text-center">
            Claude Vision will read your handwriting and extract each answer.
          </p>
        )}

        {error && <p className="text-red-500 text-sm mt-3">{error}</p>}

        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="mt-5 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-3 rounded-lg transition"
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Extracting answers with AI…
            </span>
          ) : 'Upload & Extract Answers'}
        </button>
      </div>
    )
  }

  // ── Scoring stage ─────────────────────────────────────────────────────────
  if (stage === 'scoring') {
    return (
      <div className="max-w-lg mx-auto mt-20 text-center">
        <svg className="animate-spin h-10 w-10 mx-auto text-blue-500 mb-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        <p className="text-xl font-semibold text-gray-700">Scoring your answers…</p>
        <p className="text-sm text-gray-400 mt-2">Claude is evaluating each answer against the rubric.</p>
      </div>
    )
  }

  // ── Confirmation stage ────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto mt-8 pb-16">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-800">Confirm Extracted Answers</h1>
        <p className="text-sm text-gray-500 mt-1">
          {lowConfItems.length} answer{lowConfItems.length !== 1 ? 's' : ''} had low OCR confidence.
          Please check and correct if needed.
        </p>
      </div>

      <div className="space-y-4">
        {lowConfItems.map(item => (
          <div key={item.question_id} className="bg-white rounded-xl border shadow-sm p-5">
            <div className="flex items-start justify-between mb-2">
              <p className="text-xs font-semibold text-gray-500 uppercase">Q{item.sequence}</p>
              <ConfidenceBadge conf={item.confidence} />
            </div>
            <p className="text-sm text-gray-700 mb-3 line-clamp-2">{item.question_text}</p>

            <label className="block text-xs font-medium text-gray-500 mb-1">Extracted answer</label>
            <textarea
              className="w-full border-2 border-gray-200 rounded-lg px-3 py-2 text-sm focus:border-blue-500 outline-none resize-none"
              rows={3}
              value={corrections[item.question_id] ?? item.ocr_text}
              onChange={e => setCorrections(prev => ({ ...prev, [item.question_id]: e.target.value }))}
            />
            <p className="text-xs text-gray-400 mt-1">
              Edit above if the extraction is wrong. Leave as-is to confirm.
            </p>
          </div>
        ))}
      </div>

      {error && <p className="text-red-500 text-sm mt-4">{error}</p>}

      <button
        onClick={handleConfirmAndScore}
        disabled={submitting}
        className="mt-6 w-full bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white font-semibold py-3 rounded-lg transition"
      >
        {submitting ? 'Scoring…' : `Confirm & Score (${lowConfItems.length} answers confirmed)`}
      </button>
    </div>
  )
}
