import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

interface RequireAuthProps {
  /** When set, only these roles may see the route; others get a "no access" message. */
  roles?: string[]
}

export function RequireAuth({ roles }: RequireAuthProps) {
  const { t } = useTranslation()
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {t('common.loading')}
      </p>
    )
  }
  if (status === 'anon' || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <p role="alert" className="p-6 text-danger">
        {t('auth.forbidden')}
      </p>
    )
  }
  return <Outlet />
}
