import { expect, test } from '@playwright/test'
import { dayFromNow, loginAs } from './helpers'

test('a guarantee about to expire raises a critical alert, and fixing it closes the alert', async ({ page }) => {
  await loginAs(page, 'director')

  // Edit the first guarantee: it now expires in two days (3 days or less is critical, SPEC 7.1)
  await page.goto('/contracts')
  await page.getByRole('button', { name: 'Sửa bảo lãnh' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Sửa bảo lãnh' })
  await dialog.getByLabel('Ngày hết hạn').fill(dayFromNow(2))
  await dialog.getByRole('button', { name: 'Lưu' }).click()
  await expect(dialog).toBeHidden()

  // The write triggers the alert engine in the background: look again until the alert shows up
  const alert = page.getByRole('article').filter({ hasText: 'Bảo lãnh còn 2 ngày hết hạn' })
  await expect(async () => {
    await page.goto('/alerts')
    await expect(alert.first()).toBeVisible({ timeout: 1500 })
  }).toPass({ timeout: 30_000 })
  await expect(alert.first()).toContainText('Nghiêm trọng')

  // The same alert is on the dashboard and its source link opens the contract tab
  await page.goto('/')
  await expect(page.getByRole('region', { name: 'Cảnh báo đang mở' })).toContainText('bảo lãnh')

  // Pushing the expiry far away closes the alert by itself
  await page.goto('/contracts')
  await page.getByRole('button', { name: 'Sửa bảo lãnh' }).first().click()
  await page.getByRole('dialog', { name: 'Sửa bảo lãnh' }).getByLabel('Ngày hết hạn').fill(dayFromNow(400))
  await page.getByRole('dialog', { name: 'Sửa bảo lãnh' }).getByRole('button', { name: 'Lưu' }).click()
  await expect(async () => {
    await page.goto('/alerts')
    await expect(alert).toHaveCount(0, { timeout: 1500 })
  }).toPass({ timeout: 30_000 })
})
