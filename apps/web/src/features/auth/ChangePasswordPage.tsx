import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { api, ApiError } from '@/lib/api'
import { useAuth } from './AuthContext'
import { inputClass, primaryButton } from './LoginPage'

const schema = z
  .object({
    current_password: z.string().min(1, 'auth.passwordRequired'),
    new_password: z
      .string()
      .min(10, 'auth.passwordRule')
      .regex(/[A-Za-z]/, 'auth.passwordRule')
      .regex(/\d/, 'auth.passwordRule'),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ['confirm'], message: 'auth.passwordMismatch' })
type Values = z.infer<typeof schema>

export function ChangePasswordPage() {
  const { t } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: Values) => {
    setServerError(null)
    try {
      await api.post('/auth/change-password', {
        current_password: values.current_password,
        new_password: values.new_password,
      })
      // The server revokes every token on password change, so sign in again.
      await logout()
      navigate('/login', { replace: true })
    } catch (err) {
      setServerError(
        err instanceof ApiError && err.code === 'wrong_password' ? t('auth.wrong_password') : t('common.error'),
      )
    }
  }

  const field = (name: keyof Values, label: string, autoComplete: string) => (
    <div>
      <label htmlFor={name} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      <input
        id={name}
        type="password"
        autoComplete={autoComplete}
        className={inputClass}
        aria-invalid={!!errors[name]}
        {...register(name)}
      />
      {errors[name] && (
        <p role="alert" className="mt-1 text-sm text-danger">
          {t(errors[name]?.message ?? '')}
        </p>
      )}
    </div>
  )

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-8">
      <h1 className="mb-2 text-xl font-semibold md:text-2xl">{t('auth.changeTitle')}</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        {field('current_password', t('auth.currentPassword'), 'current-password')}
        {field('new_password', t('auth.newPassword'), 'new-password')}
        <p className="-mt-2 text-sm text-muted-foreground">{t('auth.passwordRule')}</p>
        {field('confirm', t('auth.confirmPassword'), 'new-password')}
        {serverError && (
          <p role="alert" className="text-sm text-danger">
            {serverError}
          </p>
        )}
        <button type="submit" disabled={isSubmitting} className={primaryButton}>
          {t('common.save')}
        </button>
      </form>
    </main>
  )
}
