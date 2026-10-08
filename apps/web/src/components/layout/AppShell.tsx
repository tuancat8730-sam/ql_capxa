import { MoreHorizontal, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'
import { GlobalSearch } from '@/features/search/GlobalSearch'
import { useAlertBadge } from '@/features/alerts/useAlertCount'
import { startAutoSync } from '@/lib/offline'
import { OfflineBanner } from './OfflineBanner'
import { useProjects } from '@/features/projects/ProjectContext'
import { type NavItem, navFor } from './nav'
import { ProjectSwitcher } from './ProjectSwitcher'

const touchTarget = 'min-h-11 min-w-11'

function BottomNavLink({ item, badge = 0 }: { item: NavItem; badge?: number }) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      aria-label={badge > 0 ? `${t(item.labelKey)} (${badge})` : t(item.labelKey)}
      className={({ isActive }) =>
        `relative flex flex-1 flex-col items-center justify-center gap-0.5 text-xs ${touchTarget} ${
          isActive ? 'text-primary font-semibold' : 'text-muted-foreground'
        }`
      }
    >
      <Icon size={20} aria-hidden />
      <span>{t(item.labelKey)}</span>
      {badge > 0 && (
        <span aria-hidden className="absolute right-1/4 top-1 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-semibold text-white">
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </NavLink>
  )
}

function MoreSheet({ items, onClose }: { items: NavItem[]; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <div role="dialog" aria-modal="true" aria-label={t('nav.more')} className="fixed inset-0 z-40">
      <button
        type="button"
        aria-label={t('common.close')}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="absolute inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t-2xl bg-background p-4 pb-8">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{t('nav.more')}</h2>
          <button
            type="button"
            aria-label={t('common.close')}
            className={`${touchTarget} flex items-center justify-center`}
            onClick={onClose}
          >
            <X size={20} aria-hidden />
          </button>
        </div>
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {items.map((item) => {
            const Icon = item.icon
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onClose}
                  className="flex min-h-20 flex-col items-center justify-center gap-1 rounded-md border border-border p-2 text-center text-sm"
                >
                  <Icon size={20} aria-hidden />
                  {t(item.labelKey)}
                </NavLink>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const [moreOpen, setMoreOpen] = useState(false)
  const alertBadge = useAlertBadge()
  const { current } = useProjects()
  const nav = navFor(current?.modules)

  // Send queued daily logs on start, when the network returns and periodically (SPEC 15.7).
  useEffect(() => startAutoSync(), [])

  return (
    <div className="min-h-dvh md:pl-16 lg:pl-60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-16 flex-col border-r border-border bg-background md:flex lg:w-60">
        <div className="p-4 text-lg font-bold lg:text-xl">
          <span className="lg:hidden">SGM</span>
          <span className="hidden lg:inline">{t('app.name')}</span>
          <span className="ml-1 hidden text-xs font-normal text-muted-foreground lg:inline">v{__APP_VERSION__}</span>
        </div>
        <nav aria-label={t('app.name')} className="flex-1 overflow-y-auto px-2">
          <ul className="space-y-1">
            {nav.all.map((item) => {
              const Icon = item.icon
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    aria-label={t(item.labelKey)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-md px-3 text-sm ${touchTarget} ${
                        isActive ? 'bg-muted font-semibold text-primary' : 'text-foreground'
                      }`
                    }
                  >
                    <Icon size={20} aria-hidden />
                    <span className="hidden lg:inline">{t(item.labelKey)}</span>
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>

      <main className="mx-auto w-full max-w-[1440px] px-4 pb-24 pt-4 md:px-6 md:pb-8">
        <div className="mb-3 flex items-center justify-between gap-3">
          <ProjectSwitcher />
          <GlobalSearch />
        </div>
        <OfflineBanner />
        <Outlet />
      </main>

      <nav
        aria-label={t('app.name')}
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background md:hidden"
      >
        {nav.primary.map((item) => (
          <BottomNavLink key={item.to} item={item} badge={item.to === '/alerts' ? alertBadge : 0} />
        ))}
        <button
          type="button"
          aria-label={t('nav.more')}
          onClick={() => setMoreOpen(true)}
          className={`flex flex-1 flex-col items-center justify-center gap-0.5 text-xs text-muted-foreground ${touchTarget}`}
        >
          <MoreHorizontal size={20} aria-hidden />
          <span>{t('nav.more')}</span>
        </button>
      </nav>
      {moreOpen && <MoreSheet items={nav.more} onClose={() => setMoreOpen(false)} />}
    </div>
  )
}
