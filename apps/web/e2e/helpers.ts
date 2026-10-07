import { expect, type Page, type TestInfo } from '@playwright/test'

/** Password of the users made by apps/api/scripts/seed_e2e.py. */
export const E2E_PASSWORD = 'E2e-Passw0rd!x'

export async function login(page: Page, role: string, password = E2E_PASSWORD) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(`${role}@e2e.test`)
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
}

export async function loginAs(page: Page, role: string) {
  await login(page, role)
  await expect(page).toHaveURL('/')
}

/** Data written by a test must not collide across the mobile/tablet/desktop runs. */
export function unique(info: TestInfo, label: string): string {
  return `${label} ${info.project.name} ${Date.now()}`
}

/** Yyyy-mm-dd of today plus `days`, in local time (the app compares calendar dates). */
export function dayFromNow(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
