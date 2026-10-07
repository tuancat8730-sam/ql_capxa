import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('wrong password is refused with a clear message, the right one opens the dashboard', async ({ page }) => {
  await login(page, 'director', 'sai-mat-khau')
  await expect(page.getByRole('alert')).toContainText('Email hoặc mật khẩu không đúng')
  await expect(page).toHaveURL(/\/login/)

  await login(page, 'director')
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('heading', { name: 'Tổng quan dự án' })).toBeVisible()
  const strip = page.getByRole('region', { name: 'Tám gói thầu' })
  await expect(strip.getByRole('link')).toHaveCount(8)
  await expect(strip.getByRole('link', { name: /Gói 03/ })).toContainText('Chưa có hợp đồng')
})

test('pages need a login and the session survives a reload', async ({ page }) => {
  await page.goto('/risks')
  await expect(page).toHaveURL(/\/login/)

  // signing in sends the user back to the page they asked for
  await login(page, 'viewer')
  await expect(page).toHaveURL(/\/risks$/)
  await expect(page.getByRole('heading', { name: 'Sổ rủi ro' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Sổ rủi ro' })).toBeVisible()
})

test('a role without access sees a message, not the page', async ({ page }) => {
  await login(page, 'viewer')
  await page.waitForURL('/')
  await page.goto('/admin/audit')
  await expect(page.getByRole('alert')).toContainText('không có quyền')
})
