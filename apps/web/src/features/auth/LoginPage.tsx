import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { ApiError } from '@/lib/api'
import { useAuth } from './AuthContext'

const schema = z.object({
  email: z.string().trim().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, 'auth.emailInvalid'),
  password: z.string().min(1, 'auth.passwordRequired'),
})
type Values = z.infer<typeof schema>

export const inputClass =
  'min-h-11 w-full rounded-md border border-border bg-background px-3 text-base focus:outline-2 focus:outline-primary'
export const primaryButton =
  'min-h-11 w-full rounded-md bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-60 md:w-auto'

export function LoginPage() {
  const { t } = useTranslation()
  const { login, status, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) })

  if (status === 'authed' && user) return <Navigate to={from} replace />

  const onSubmit = async (values: Values) => {
    setServerError(null)
    try {
      await login(values.email, values.password)
      navigate(from, { replace: true })
    } catch (err) {
      const code = err instanceof ApiError ? err.code : 'error'
      setServerError(
        code === 'invalid_credentials' || code === 'account_locked' ? t(`auth.${code}`) : t('common.error'),
      )
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-8">
      <h1 className="mb-1 text-xl font-semibold md:text-2xl">{t('app.name')}</h1>
      <h2 className="mb-6 text-muted-foreground">{t('auth.loginTitle')}</h2>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium">
            {t('auth.email')}
          </label>
          <input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="username"
            className={inputClass}
            aria-invalid={!!errors.email}
            {...register('email')}
          />
          {errors.email && (
            <p role="alert" className="mt-1 text-sm text-danger">
              {t(errors.email.message ?? '')}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium">
            {t('auth.password')}
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={inputClass}
            aria-invalid={!!errors.password}
            {...register('password')}
          />
          {errors.password && (
            <p role="alert" className="mt-1 text-sm text-danger">
              {t(errors.password.message ?? '')}
            </p>
          )}
        </div>
        {serverError && (
          <p role="alert" className="text-sm text-danger">
            {serverError}
          </p>
        )}
        <button type="submit" disabled={isSubmitting} className={primaryButton}>
          {isSubmitting ? t('auth.submitting') : t('auth.submit')}
        </button>
      </form>
    </main>
  )
}
