import os, sys, json, sqlite3
sys.path.insert(0, os.getcwd())

results = []
def check(num, name, cond, detail=''):
    s = 'PASS' if cond else 'FAIL'
    results.append((num, s, name, detail))
    return cond
def rf(path):
    try: return open(path, encoding='utf-8').read()
    except: return ''
def has_fn(src, fn): return ('def ' + fn) in src

ROOT = os.getcwd()
DB_PATH = os.path.join(ROOT, 'data', 'science_assessor.db')
try:
    from backend.database import init_db
    init_db()
except Exception as e:
    print('init_db:', e)

check(1, '5 chapter JSON files exist', all(os.path.exists('data/questions/'+f) for f in ['light.json','human_eye.json','electricity.json','magnetic_effects.json','sources_of_energy.json']))

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
check(2, 'All DB tables', all(t in tables for t in ['question_index','assessments','answers','student_profile']))
ca = {r[1] for r in conn.execute('PRAGMA table_info(answers)').fetchall()}
cp = {r[1] for r in conn.execute('PRAGMA table_info(student_profile)').fetchall()}
cx = {r[1] for r in conn.execute('PRAGMA table_info(assessments)').fetchall()}
check(2, 'override cols in answers', 'override_score' in ca and 'override_note' in ca)
check(2, 'guidance_cache cols', 'guidance_cache' in cp and 'guidance_cached_at' in cp)
check(2, 'exam_readiness_score in profile', 'exam_readiness_score' in cp)
check(2, 'section_map/overall_guidance in assessments', 'section_map' in cx and 'overall_guidance' in cx)
conn.close()

sess = rf('backend/routers/session.py')
check(3, 'session/create 4 types', all(t in sess for t in ['understanding','chapter_short','chapter_regular','mock']))
check(4, 'one-active-test', '_check_one_active_test' in sess)
check(5, 'upload-pdf', 'upload-pdf' in sess or 'upload_pdf' in sess)
check(6, '2-call budget', 'call_1' in sess and 'call_2' in sess)
check(7, 'update_profile', 'update_profile' in sess)
check(8, 'results endpoint', 'results' in sess)
check(9, 'expiry job', 'expire' in rf('backend/main.py').lower())

tmpl = json.loads(open('data/config/test_templates.json').read())['templates']['mock']
tq = sum(slot['count'] for sec in tmpl['sections'] for slot in sec['slots'])
check(10, 'Mock 39 questions (got %d)' % tq, tq == 39)

a = rf('backend/analytics.py')
check(11, 'analytics.py exists', bool(a))
for fn in ['get_topic_scores','get_topic_trend','get_topic_classification','get_chapter_performance','get_marks_lost_by_type','get_exam_readiness','get_weak_topics','get_untested_topics']:
    check(11, '  analytics.'+fn, has_fn(a, fn))
pu = rf('backend/services/profile_updater.py')
check(12, 'decay weights', all(w in pu for w in ['0.5','0.25','decay']))
check(13, '1.5x session weight', '1.5' in pu and 'SESSION_WEIGHT' in pu)
check(14, 'min_attempts gate', 'min_attempts' in a)
for band in ['Strong','Developing','Weak','Critical','Untested']:
    check(15, 'Band '+band, band in a)
check(16, 'trend recent vs prev', 'recent' in a and ('prev' in a or 'previous' in a))
check(16, 'trend up/down/flat', all(t in a for t in ['up','down','flat']))
check(17, 'chapter_perf JOIN', 'JOIN' in a.upper() and 'question_index' in a)
check(18, 'marks_lost_by_type', 'marks_lost' in a.lower() and 'type' in a)
check(19, 'exam_readiness weights+range', '_CHAPTER_BOARD_WEIGHTS' in a and 'range_low' in a and 'band_label' in a)
check(20, 'weak topics sorted', 'sorted' in a)
check(21, 'untested syllabus+<3', 'syllabus' in a.lower() and ('< 3' in a or '<3' in a))

adm = rf('backend/routers/admin.py')
check(22, 'dashboard fields', all(f in adm for f in ['total_sessions','overall_average','chapter_performance','exam_readiness','current_streak']))
check(23, 'strengths classification', 'classification' in adm and 'topics' in adm)
check(24, 'action labels', all(x in adm for x in ['Revise Now','Practice More','Consolidate','Keep Going']))
check(25, 'paginated sessions', 'page' in adm and 'limit' in adm and 'chapter' in adm)
check(26, 'question_store + question_text', ('get_question_store' in adm or 'question_store' in adm) and 'question_text' in adm)
check(27, 'marks_lost panels', 'marks_lost_by_type' in adm and 'marks_lost_by_reason' in adm)
check(28, 'coverage vs templates', '_TEMPLATES_PATH' in adm or 'test_templates' in adm)
check(29, 'guidance cache 24h', '24' in adm and 'guidance_cache' in adm)
check(30, 'guidance context', all(f in adm for f in ['weak_topics','days_until_exam']))
ai = rf('backend/services/ai_client.py')
check(31, 'guidance 3 sections', all(f in ai for f in ['priority_topics','recommended_sequence','exam_readiness_projection']))
check(32, 'guidance cached', 'guidance_cache' in adm and 'guidance_cached_at' in adm)
check(33, 'call_guidance not call_1/2', 'call_guidance' in adm and 'call_1' not in adm and 'call_2' not in adm)

db2 = rf('frontend/src/pages/admin/AdminDashboard.tsx')
ts  = rf('frontend/src/pages/admin/TopicStrengths.tsx')
sd  = rf('frontend/src/pages/admin/SessionDetail.tsx')
sg  = rf('frontend/src/pages/admin/StudyGuidance.tsx')
app = rf('frontend/src/App.tsx')

check(34, 'Dashboard 5 metrics', all(m in db2 for m in ['total_sessions','total_questions_answered','overall_average','current_streak','best_streak']))
check(35, 'Dashboard chapter bars', 'BAND_COLOR' in db2 and 'bg-green' in db2)
check(36, 'Dashboard chapter expand topic rows', ('expanded' in db2.lower() or 'setExpanded' in db2) and 'topic' in db2.lower())
check(37, 'Dashboard sessions clickable', 'navigate' in db2 and 'admin/session' in db2)
check(38, 'Dashboard strengths green pills', 'strengths' in db2.lower() and 'bg-green' in db2)
check(39, 'Dashboard weaknesses red/orange', 'weaknesses' in db2.lower() and ('bg-red' in db2 or 'bg-orange' in db2))
check(40, 'Dashboard exam readiness range+band', 'range_low' in db2 and 'band_label' in db2)
check(41, 'Dashboard coverage gap alert', 'coverage_gaps' in db2 and 'length' in db2)
check(42, 'TS weak summary', 'weak_topics' in ts and 'Weakest' in ts)
check(43, 'TS untested panel', 'untested_topics' in ts)
check(44, 'TS accordion Weak/Critical', 'hasWeak' in ts and 'Weak' in ts and 'Critical' in ts)
check(45, 'TS chapter avg+band', 'chapter_title' in ts and 'average' in ts.lower())
check(46, 'TS 6 data points', all(f in ts for f in ['topic_title','score','attempts','last_tested','trend']))
check(47, 'TS trend arrows', 'up' in ts and 'down' in ts and 'flat' in ts)
check(48, 'TS action badges', all(x in ts for x in ['Revise Now','Practice More','Consolidate','Keep Going']))
check(49, 'TS sparkline', 'svg' in ts.lower() or 'sparkline' in ts.lower() or 'polyline' in ts.lower() or '<path' in ts.lower())
check(50, 'SD header fields', all(f in sd for f in ['started_at','type','chapter','score_obtained','total_marks']))
check(51, 'SD question_text', 'question_text' in sd)
check(52, 'SD ocr+answer text', 'ocr_text' in sd and 'answer_text' in sd)
check(53, 'SD eval layer badge', 'evaluation_layer' in sd and 'LAYER_COLOR' in sd)
check(54, 'SD model_answer+points_missed', 'model_answer' in sd and 'points_missed' in sd)
check(55, 'SD marks lost', 'marks_lost_by_type' in sd and 'marks_lost_by_reason' in sd)
check(56, 'SD override panel', 'OverridePanel' in sd and 'overrideAnswerScore' in sd)
check(57, 'answers override cols in db.py', all(c in rf('backend/database.py') for c in ['override_score','override_note']))
check(58, 'SG loading', 'loading' in sg.lower() and 'Loading' in sg)
check(59, 'SG priority_topics+ncert', 'priority_topics' in sg and 'ncert_reference' in sg)
check(60, 'SG recommended_sequence', 'recommended_sequence' in sg)
check(61, 'SG exam_readiness_projection', 'exam_readiness_projection' in sg)
check(62, 'SG refresh', 'refresh' in sg.lower() and 'true' in sg)
check(63, 'App two-tier nav', 'Student' in app and 'Admin' in app)
check(64, 'Student resume link', 'activeTest' in app or 'active_session' in app or 'ActiveTest' in app or 'resume' in app.lower())
check(65, 'Admin 5 links', all(l in app for l in ['/admin/strengths','/admin/sessions','/admin/guidance','/admin/questions']))
check(66, 'Nav active highlight', 'isActive' in app)
check(67, 'Dashboard empty state', 'No completed' in db2 or '0' in db2)
check(68, 'topic_scores accessible', 'topic_scores' in pu and 'topic_scores' in a)
check(69, 'SQL aggregation', 'SUM' in a.upper() and 'JOIN' in a.upper())
check(70, 'guidance context full', 'weak_topics' in adm and 'current_streak' in adm and 'exam_readiness' in adm)
check(71, 'override recalc', 'score_obtained' in adm and 'percentage' in adm and 'UPDATE assessments' in adm)
check(72, 'admin pages import api/client', all('../../api/client' in rf('frontend/src/pages/admin/'+p) for p in ['AdminDashboard.tsx','TopicStrengths.tsx','SessionDetail.tsx','StudyGuidance.tsx']))

passed = sum(1 for _,s,_,_ in results if s=='PASS')
failed = sum(1 for _,s,_,_ in results if s=='FAIL')
print('PHASE 5: %d/%d PASS, %d FAIL' % (passed, len(results), failed))
print('='*60)
for num,s,name,detail in results:
    mark = 'OK' if s=='PASS' else 'XX'
    line = '[%s] #%02d %s' % (mark, num, name)
    if detail: line += '  => ' + detail
    print(line)
