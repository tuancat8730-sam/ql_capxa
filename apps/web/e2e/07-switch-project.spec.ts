import { expect, test } from '@playwright/test'
import { loginAs } from './helpers'

// `multi@e2e.test` is director in the commune project and technician in SGD-HCM (seed_e2e.py).
test('switch to SGD-HCM, record progress on the schedule, switch back', async ({ page }) => {
  await loginAs(page, 'multi')

  const switcher = page.getByRole('combobox', { name: 'Chuyển dự án' })
  await expect(switcher).toBeVisible()
  await expect(switcher.locator('option')).toHaveText(['Cấp xã Lâm Đồng', 'SGD-HCM'])

  // the other project has its own home page and its own menu
  await switcher.selectOption({ label: 'SGD-HCM' })
  await expect(page.getByText('Tiến độ thực tế')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Tiến độ theo giai đoạn' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Gói thầu' })).toHaveCount(0)

  // the choice survives a reload (kept in the browser)
  await page.reload()
  await expect(page.getByText('Tiến độ thực tế')).toBeVisible()

  await page.goto('/schedule')
  const row = page.getByRole('button', { name: /I\.1 Họp khởi động/ })
  await row.click()
  const dialog = page.getByRole('dialog', { name: /I\.1 · Họp khởi động/ })
  await dialog.getByRole('button', { name: '100%' }).click()
  await dialog.getByRole('button', { name: 'Lưu' }).click()
  await expect(dialog).toBeHidden()
  await expect(row).toHaveAccessibleName(/Hoàn thành/)

  // a technician records progress but cannot touch the commune project's data through this project
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Chuyển dự án' }).selectOption({ label: 'Cấp xã Lâm Đồng' })
  await page.goto('/packages')
  await expect(page.getByRole('link', { name: /Gói 04/ }).first()).toBeVisible()
})

test('a person in one project sees no switcher', async ({ page }) => {
  await loginAs(page, 'director')
  await expect(page.getByRole('combobox', { name: 'Chuyển dự án' })).toHaveCount(0)
  await expect(page.getByText('Cấp xã Lâm Đồng').first()).toBeVisible()
})
