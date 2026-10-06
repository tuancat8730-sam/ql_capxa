import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function ProfilePage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) return null

  return (
    <section className="max-w-md space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('auth.profileTitle')}</h1>
      <dl className="space-y-2 rounded-md border border-border p-4">
        <div>
          <dt className="text-sm text-muted-foreground">{t('users.fullName')}</dt>
          <dd className="font-medium">{user.full_name}</dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">{t('auth.email')}</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">{t('users.role')}</dt>
          <dd>{t(`roles.${user.role}`)}</dd>
        </div>
      </dl>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Link
          to="/change-password"
          className="flex min-h-11 items-center justify-center rounded-md border border-border px-4"
        >
          {t('auth.changeTitle')}
        </Link>
        <button
          type="button"
          className="min-h-11 rounded-md border border-border px-4"
          onClick={async () => {
            await logout()
            navigate('/login', { replace: true })
          }}
        >
          {t('auth.logout')}
        </button>
      </div>
    </section>
  )
}
