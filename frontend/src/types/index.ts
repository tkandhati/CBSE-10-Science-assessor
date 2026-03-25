export interface Option {
  text: string
  is_correct?: boolean
}

export interface Rubric {
  keywords: string[]
  key_points: string[]
  formula: string | null
  expected_answer: string
  diagram_required: boolean
  diagram_checklist: string[]
  partial_marks: Record<string, number>
}

export interface GeneratedParams {
  variables: Record<string, number>
  expected_answer: number | null
  expected_answer_str: string | null
  formula_expression: string
  units: string
  answer_precision: number
}

export interface Question {
  id: string
  sequence: number
  text: string
  type: 'mcq' | 'short' | 'numerical' | 'long' | 'diagram' | 'assertion_reason' | 'case_based'
  difficulty: number
  marks: number
  options: Option[] | null
  correct_option_index: number | null
  expected_answer: number | null
  expected_answer_str: string | null
  diagram_path: string | null
  generated_params: GeneratedParams | null
  rubric: Rubric | null
  section?: string   // mock only: "A" | "B" | "C" | "D" | "E"
}

export interface SessionResponse {
  session_id: string
  status: string
  type: string
  chapter: string
  topic: string | null
  total_questions: number
  total_marks: number
  questions: Question[]
  duration_minutes?: number
  section_map?: Record<string, string>
}

export interface AnswerSubmission {
  question_id: string
  answer_text?: string
  selected_option?: number
  time_seconds: number
}

export interface Feedback {
  keywords_found: string[]
  points_covered: string[]
  points_missed: string[]
  comment: string
}

export interface QuestionResult {
  question_id: string
  question_text: string
  student_answer: string | null
  selected_option: number | null
  score: number
  max_marks: number
  is_correct: boolean
  evaluation_layer: string
  feedback: Feedback
  suggestions: string | null
  model_answer: string
  key_points: string[]
  section?: string
  chapter?: string
}

export interface SectionBreakdown {
  score: number
  max_marks: number
}

export interface SessionResults {
  session_id: string
  type: string
  chapter: string
  topic: string | null
  total_marks: number
  score_obtained: number
  percentage: number
  status: string
  results: QuestionResult[]
  xp_earned?: number
  current_streak: number
  total_xp: number
  topic_scores: Record<string, number>
  section_breakdown?: Record<string, SectionBreakdown>
  chapter_breakdown?: Record<string, SectionBreakdown>
  exam_readiness_score?: number
  overall_guidance?: string
  duration_minutes?: number
  new_badges?: string[]
  leveled_up?: boolean
  current_level?: number
}

export interface OCRItem {
  question_id: string
  sequence: number
  question_text: string
  ocr_text: string
  confidence: number
}

export interface UploadOCRResult {
  session_id: string
  status: string
  questions_ocrd: number
  low_confidence: OCRItem[]
}

export interface ChapterInfo {
  id: string
  title: string
  ncert_chapter: number
  board_weightage: number
  topics: { id: string; title: string; board_weightage: number }[]
}

// ── Admin types ────────────────────────────────────────────────────────────────

export interface ChapterPerf {
  title: string
  average: number
  attempts: number
  band: 'Strong' | 'Developing' | 'Weak' | 'Critical' | 'Untested'
}

export interface WeakTopic {
  topic_key: string
  topic_title: string
  chapter_id: string
  chapter_title: string
  score: number
  attempts: number
  last_tested: string | null
}

export interface ExamReadiness {
  score: number
  range_low: number
  range_high: number
  band_label: string
}

export interface CoverageGap {
  chapter: string
  template: string
  type: string
  needed: number
  available: number
  gap: number
}

export interface AdminDashboardData {
  total_sessions: number
  total_questions_answered: number
  overall_average: number
  current_streak: number
  best_streak: number
  chapter_performance: Record<string, ChapterPerf>
  recent_sessions: AdminSession[]
  strengths: { topic_key: string; score: number }[]
  weaknesses: WeakTopic[]
  exam_readiness: ExamReadiness
  coverage_gaps: CoverageGap[]
}

export interface AdminSession {
  id: string
  type: string
  chapter: string
  topic: string | null
  total_marks: number
  score_obtained: number
  percentage: number
  status: string
  started_at: string
  completed_at: string | null
  duration_seconds: number
}

export interface TopicInfo {
  topic_title: string
  chapter_id: string
  chapter_title: string
  band: 'Strong' | 'Developing' | 'Weak' | 'Critical' | 'Untested'
  score: number
  attempts: number
  last_tested: string | null
  trend: 'up' | 'down' | 'flat'
  recommended_action: string
}

export interface TopicStrengthsData {
  topics: Record<string, TopicInfo>
  weak_topics: WeakTopic[]
  untested_topics: {
    topic_key: string
    topic_title: string
    chapter_id: string
    chapter_title: string
    attempts: number
  }[]
}

export interface AdminAnswerDetail {
  id: string
  question_id: string
  question_text: string
  question_type: string
  answer_text: string | null
  selected_option: number | null
  ocr_text: string | null
  score: number
  max_marks: number
  override_score: number | null
  override_note: string | null
  evaluation_layer: string
  feedback: { keywords_found: string[]; points_covered: string[]; points_missed: string[]; comment: string }
  suggestions: string[]
  model_answer: string
  key_points: string[]
}

export interface AdminSessionDetail {
  session: AdminSession & { section_map: Record<string, string>; overall_guidance: string }
  answers: AdminAnswerDetail[]
  marks_lost_by_type: Record<string, number>
  marks_lost_by_reason: Record<string, number>
}

export interface PriorityTopic {
  topic_key: string
  topic_name: string
  current_score: number
  reason: string
  ncert_reference: string
}

export interface DayPlan {
  day: number
  session_type: string
  focus: string
  note: string
}

export interface GuidanceData {
  priority_topics: PriorityTopic[]
  recommended_sequence: DayPlan[]
  exam_readiness_projection: {
    current_score: number
    target_score: number
    marks_recoverable: number
    what_if: string
  }
  cached_at: string
}

// ── Gamification types ─────────────────────────────────────────────────────

export interface StudentProfile {
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

export interface BadgeInfo {
  id: string
  name: string
  description: string
  icon: string
  earned: boolean
  earned_at: string | null
}

export interface ReviewQueueQuestion {
  id: string
  chapter: string
  topic: string
  type: string
  difficulty: number
  marks: number
  text: string
  options: { text: string; is_correct: boolean }[] | null
  rubric: { keywords: string[]; key_points: string[]; expected_answer: string } | null
  source: string
  board_years: string
  tags: string
  added_at: string
  status: string
}

export interface QBankStats {
  total: number
  approved: number
  pending_review: number
  by_chapter: Record<string, { approved: number; pending: number; total: number }>
  by_type: Record<string, number>
  by_difficulty: Record<string, number>
}

export interface LiveQuestion {
  id: string
  chapter: string
  topic: string
  type: string
  difficulty: number
  marks: number
  times_served: number
  last_served_at: string | null
  text_preview: string
  full_text: string
  options: { text: string; is_correct: boolean }[] | null
  expected_answer: string
  key_points: string[]
  tags: string
}
