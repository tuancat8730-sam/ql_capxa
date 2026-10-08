import { lazy, type ReactNode, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { allNav } from './components/layout/nav'
import { ChangePasswordPage } from './features/auth/ChangePasswordPage'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAuth } from './features/auth/RequireAuth'
import { ProjectProvider, useProjects } from './features/projects/ProjectContext'

// Route-level code splitting keeps the first load small on slow 4G (SPEC 15.1, 15.10).
const DashboardPage = lazy(() => import('./features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const AlertsPage = lazy(() => import('./features/alerts/AlertsPage').then((m) => ({ default: m.AlertsPage })))
const OutgoingDocsPage = lazy(() => import('./features/docnumbers/OutgoingDocsPage').then((m) => ({ default: m.OutgoingDocsPage })))
const AuditPage = lazy(() => import('./features/audit/AuditPage').then((m) => ({ default: m.AuditPage })))
const SettingsPage = lazy(() => import('./features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const ProjectsPage = lazy(() => import('./features/admin/ProjectsPage').then((m) => ({ default: m.ProjectsPage })))
const UsersPage = lazy(() => import('./features/admin/UsersPage').then((m) => ({ default: m.UsersPage })))
const ProfilePage = lazy(() => import('./features/auth/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const DocumentsPage = lazy(() => import('./features/documents/DocumentsPage').then((m) => ({ default: m.DocumentsPage })))
const GuaranteesPage = lazy(() => import('./features/finance/GuaranteesPage').then((m) => ({ default: m.GuaranteesPage })))
const PaymentsPage = lazy(() => import('./features/finance/PaymentsPage').then((m) => ({ default: m.PaymentsPage })))
const PackageDetailPage = lazy(() => import('./features/packages/PackageDetailPage').then((m) => ({ default: m.PackageDetailPage })))
const ProgressPage = lazy(() => import('./features/progress/ProgressPage').then((m) => ({ default: m.ProgressPage })))
const DailyLogPage = lazy(() => import('./features/progress/DailyLogPage').then((m) => ({ default: m.DailyLogPage })))
const RisksPage = lazy(() => import('./features/risks/RisksPage').then((m) => ({ default: m.RisksPage })))
const IssuesPage = lazy(() => import('./features/issues/IssuesPage').then((m) => ({ default: m.IssuesPage })))
const MeetingsPage = lazy(() => import('./features/meetings/MeetingsPage').then((m) => ({ default: m.MeetingsPage })))
const ChangeRequestsPage = lazy(() =>
  import('./features/meetings/ChangeRequestsPage').then((m) => ({ default: m.ChangeRequestsPage })),
)
const DeliveryOverviewPage = lazy(() => import('./features/delivery/DeliveryOverviewPage').then((m) => ({ default: m.DeliveryOverviewPage })))
const SchedulePage = lazy(() => import('./features/delivery/SchedulePage').then((m) => ({ default: m.SchedulePage })))
const WeeklyReportsPage = lazy(() => import('./features/delivery/WeeklyReportsPage').then((m) => ({ default: m.WeeklyReportsPage })))
const DecisionsPage = lazy(() => import('./features/delivery/DecisionsPage').then((m) => ({ default: m.DecisionsPage })))
const DeliveryRisksPage = lazy(() => import('./features/delivery/DeliveryRisksPage').then((m) => ({ default: m.DeliveryRisksPage })))
const PackagesPage = lazy(() => import('./features/packages/PackagesPage').then((m) => ({ default: m.PackagesPage })))

/** The same address shows a different page depending on what kind of project is open. */
function ByProjectType({ procurement, software }: { procurement: ReactNode; software: ReactNode }) {
  const { current } = useProjects()
  return current?.project_type === 'software_delivery' ? software : procurement
}

function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="text-xl font-semibold md:text-2xl">{t(titleKey)}</h1>
      <p className="mt-2 text-muted-foreground">{t('common.empty')}</p>
    </section>
  )
}

const implemented = new Set(['/', '/alerts', '/admin/users', '/profile', '/packages', '/contracts', '/payments', '/documents', '/progress', '/daily-log', '/risks', '/issues', '/meetings', '/change-requests', '/outgoing-docs', '/admin/audit', '/admin/settings', '/admin/projects', '/schedule', '/weekly-reports', '/decisions'])

export default function App() {
  const { t } = useTranslation()
  return (
    <Suspense fallback={<p role="status" className="p-6 text-muted-foreground">{t('common.loading')}</p>}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route
          element={
            <ProjectProvider>
              <AppShell />
            </ProjectProvider>
          }
        >
          {allNav
            .filter((item) => !implemented.has(item.to))
            .map((item) => (
              <Route key={item.to} path={item.to} element={<PlaceholderPage titleKey={item.labelKey} />} />
            ))}
          <Route path="/" element={<ByProjectType procurement={<DashboardPage />} software={<DeliveryOverviewPage />} />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/weekly-reports" element={<WeeklyReportsPage />} />
          <Route path="/decisions" element={<DecisionsPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/packages" element={<PackagesPage />} />
          <Route path="/packages/:id" element={<PackageDetailPage />} />
          <Route path="/contracts" element={<GuaranteesPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/daily-log" element={<DailyLogPage />} />
          <Route path="/risks" element={<ByProjectType procurement={<RisksPage />} software={<DeliveryRisksPage />} />} />
          <Route path="/issues" element={<IssuesPage />} />
          <Route path="/meetings" element={<MeetingsPage />} />
          <Route path="/change-requests" element={<ChangeRequestsPage />} />
          <Route path="/outgoing-docs" element={<OutgoingDocsPage />} />
          <Route element={<RequireAuth roles={['admin']} />}>
            <Route path="/admin/users" element={<UsersPage />} />
            <Route path="/admin/projects" element={<ProjectsPage />} />
            <Route path="/admin/settings" element={<SettingsPage />} />
          </Route>
          <Route element={<RequireAuth roles={['admin', 'director']} />}>
            <Route path="/admin/audit" element={<AuditPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
    </Suspense>
  )
}
