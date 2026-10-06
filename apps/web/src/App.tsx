import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { sidebarNav } from './components/layout/nav'
import { ChangePasswordPage } from './features/auth/ChangePasswordPage'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAuth } from './features/auth/RequireAuth'

// Route-level code splitting keeps the first load small on slow 4G (SPEC 15.1, 15.10).
const UsersPage = lazy(() => import('./features/admin/UsersPage').then((m) => ({ default: m.UsersPage })))
const ProfilePage = lazy(() => import('./features/auth/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const DocumentsPage = lazy(() => import('./features/documents/DocumentsPage').then((m) => ({ default: m.DocumentsPage })))
const GuaranteesPage = lazy(() => import('./features/finance/GuaranteesPage').then((m) => ({ default: m.GuaranteesPage })))
const PaymentsPage = lazy(() => import('./features/finance/PaymentsPage').then((m) => ({ default: m.PaymentsPage })))
const PackageDetailPage = lazy(() => import('./features/packages/PackageDetailPage').then((m) => ({ default: m.PackageDetailPage })))
const ProgressPage = lazy(() => import('./features/progress/ProgressPage').then((m) => ({ default: m.ProgressPage })))
const DailyLogPage = lazy(() => import('./features/progress/DailyLogPage').then((m) => ({ default: m.DailyLogPage })))
const PackagesPage = lazy(() => import('./features/packages/PackagesPage').then((m) => ({ default: m.PackagesPage })))

function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="text-xl font-semibold md:text-2xl">{t(titleKey)}</h1>
      <p className="mt-2 text-muted-foreground">{t('common.empty')}</p>
    </section>
  )
}

const implemented = new Set(['/admin/users', '/profile', '/packages', '/contracts', '/payments', '/documents', '/progress', '/daily-log'])

export default function App() {
  const { t } = useTranslation()
  return (
    <Suspense fallback={<p role="status" className="p-6 text-muted-foreground">{t('common.loading')}</p>}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route element={<AppShell />}>
          {sidebarNav
            .filter((item) => !implemented.has(item.to))
            .map((item) => (
              <Route key={item.to} path={item.to} element={<PlaceholderPage titleKey={item.labelKey} />} />
            ))}
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/packages" element={<PackagesPage />} />
          <Route path="/packages/:id" element={<PackageDetailPage />} />
          <Route path="/contracts" element={<GuaranteesPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/daily-log" element={<DailyLogPage />} />
          <Route element={<RequireAuth roles={['admin']} />}>
            <Route path="/admin/users" element={<UsersPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
    </Suspense>
  )
}
