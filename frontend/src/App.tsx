import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Dashboard       from './pages/Dashboard'
import StartSession    from './pages/StartSession'
import TakeSession     from './pages/TakeSession'
import UploadPDF       from './pages/UploadPDF'
import Results         from './pages/Results'
import SparkSession    from './pages/SparkSession'
import AdminDashboard  from './pages/admin/AdminDashboard'
import SessionDetail   from './pages/admin/SessionDetail'
import QuestionBank    from './pages/admin/QuestionBank'
import StudyGuidance   from './pages/admin/StudyGuidance'
import TopicStrengths  from './pages/admin/TopicStrengths'

const adminLinks = [
  { to: '/admin',           label: 'Dashboard' },
  { to: '/admin/strengths', label: 'Topic Intelligence' },
  { to: '/admin/sessions',  label: 'Session History' },
  { to: '/admin/guidance',  label: 'Study Guidance' },
  { to: '/admin/questions', label: 'Question Bank' },
]

function Nav() {
  const loc = useLocation()
  const isAdmin = loc.pathname.startsWith('/admin')
  const studentLinks = [
    { to: '/', label: 'Dashboard' },
  ]

  const activeClass = 'border-b-2 border-blue-600 text-blue-700 font-semibold'
  const inactiveClass = 'text-gray-500 hover:text-gray-700'

  return (
    <nav className="bg-white border-b shadow-sm">
      {/* Tab switcher */}
      <div className="flex border-b px-6 gap-0">
        <NavLink
          to="/"
          className={`px-5 py-3 text-sm font-medium border-b-2 -mb-px transition-colors
            ${!isAdmin ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          onClick={e => isAdmin ? undefined : e.preventDefault()}
          replace
        >
          Student
        </NavLink>
        <NavLink
          to="/admin"
          className={`px-5 py-3 text-sm font-medium border-b-2 -mb-px transition-colors
            ${isAdmin ? 'border-purple-600 text-purple-700' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
        >
          Admin
        </NavLink>
      </div>

      {/* Page links */}
      <div className="flex gap-5 px-6 py-2 text-sm overflow-x-auto">
        {(isAdmin ? adminLinks : studentLinks).map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/' || link.to === '/admin'}
            className={({ isActive }) =>
              `pb-1 whitespace-nowrap transition-colors ${isActive ? activeClass : inactiveClass}`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Nav />
      <main className="p-6">
        <Routes>
          {/* Student routes */}
          <Route path="/"                    element={<Dashboard />} />
          <Route path="/spark"               element={<SparkSession />} />
          <Route path="/session/new"         element={<StartSession />} />
          <Route path="/session/:id"         element={<TakeSession />} />
          <Route path="/session/:id/upload"  element={<UploadPDF />} />
          <Route path="/session/:id/results" element={<Results />} />

          {/* Admin routes */}
          <Route path="/admin"                 element={<AdminDashboard />} />
          <Route path="/admin/session/:id"     element={<SessionDetail />} />
          <Route path="/admin/sessions"        element={<AdminSessionsPage />} />
          <Route path="/admin/questions"       element={<QuestionBank />} />
          <Route path="/admin/guidance"        element={<StudyGuidance />} />
          <Route path="/admin/strengths"       element={<TopicStrengths />} />
        </Routes>
      </main>
    </div>
  )
}

// Inline sessions-list page (just redirects to AdminDashboard with a scroll hint)
function AdminSessionsPage() {
  return <AdminDashboard showSessionsExpanded />
}
