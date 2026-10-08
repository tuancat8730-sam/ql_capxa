import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useProjects } from '@/features/projects/ProjectContext'

/** Shows the project being worked on; with several, lets the user switch (back to its home page). */
export function ProjectSwitcher() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { projects, current, select } = useProjects()
  if (!current) return <span />

  const label = current.short_name ?? current.name
  if (projects.length < 2) {
    return (
      <p className="min-w-0 truncate text-sm font-semibold" title={current.name}>
        {label}
      </p>
    )
  }
  return (
    <label className="flex min-w-0 items-center gap-2 text-sm">
      <span className="sr-only">{t('projects.switch')}</span>
      <select
        aria-label={t('projects.switch')}
        value={current.id}
        onChange={(e) => {
          select(e.target.value)
          navigate('/')
        }}
        className="min-h-11 min-w-0 max-w-[60vw] truncate rounded-md border border-border bg-background px-2 font-semibold md:max-w-xs"
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.short_name ?? p.name}
          </option>
        ))}
      </select>
    </label>
  )
}
