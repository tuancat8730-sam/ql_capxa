import { useTranslation } from 'react-i18next'
import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { sidebarNav } from './components/layout/nav'

function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()
  return (
    <section>
      <h1 className="text-xl font-semibold md:text-2xl">{t(titleKey)}</h1>
      <p className="mt-2 text-muted-foreground">{t('common.empty')}</p>
    </section>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {sidebarNav.map((item) => (
          <Route
            key={item.to}
            path={item.to}
            element={<PlaceholderPage titleKey={item.labelKey} />}
          />
        ))}
      </Route>
    </Routes>
  )
}
