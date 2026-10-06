import { useTranslation } from 'react-i18next'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { sidebarNav } from './components/layout/nav'
import { UsersPage } from './features/admin/UsersPage'
import { ChangePasswordPage } from './features/auth/ChangePasswordPage'
import { LoginPage } from './features/auth/LoginPage'
import { ProfilePage } from './features/auth/ProfilePage'
import { RequireAuth } from './features/auth/RequireAuth'
import { GuaranteesPage } from './features/finance/GuaranteesPage'
import { PaymentsPage } from './features/finance/PaymentsPage'
import { PackageDetailPage } from './features/packages/PackageDetailPage'
import { PackagesPage } from './features/packages/PackagesPage'

function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="text-xl font-semibold md:text-2xl">{t(titleKey)}</h1>
      <p className="mt-2 text-muted-foreground">{t('common.empty')}</p>
    </section>
  )
}

const implemented = new Set(['/admin/users', '/profile', '/packages', '/contracts', '/payments'])

export default function App() {
  return (
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
          <Route element={<RequireAuth roles={['admin']} />}>
            <Route path="/admin/users" element={<UsersPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}
