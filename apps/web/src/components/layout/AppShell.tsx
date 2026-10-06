import { MoreHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'
import { moreNav, type NavItem, primaryNav, sidebarNav } from './nav'

const touchTarget = 'min-h-11 min-w-11'

function BottomNavLink({ item }: { item: NavItem }) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      aria-label={t(item.labelKey)}
      className={({ isActive }) =>
        `flex flex-1 flex-col items-center justify-center gap-0.5 text-xs ${touchTarget} ${
          isActive ? 'text-primary font-semibold' : 'text-muted-foreground'
        }`
      }
    >
      <Icon size={20} aria-hidden />
      <span>{t(item.labelKey)}</span>
    </NavLink>
  )
}

function MoreSheet({ onClose }: { onClose: () => void }) {
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
          {moreNav.map((item) => {
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

  return (
    <div className="min-h-dvh md:pl-16 lg:pl-60">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-16 flex-col border-r border-border bg-background md:flex lg:w-60">
        <div className="p-4 text-lg font-bold lg:text-xl">
          <span className="lg:hidden">Q</span>
          <span className="hidden lg:inline">{t('app.name')}</span>
        </div>
        <nav aria-label={t('app.name')} className="flex-1 overflow-y-auto px-2">
          <ul className="space-y-1">
            {sidebarNav.map((item) => {
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
        <Outlet />
      </main>

      <nav
        aria-label={t('app.name')}
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-background md:hidden"
      >
        {primaryNav.map((item) => (
          <BottomNavLink key={item.to} item={item} />
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
      {moreOpen && <MoreSheet onClose={() => setMoreOpen(false)} />}
    </div>
  )
}
