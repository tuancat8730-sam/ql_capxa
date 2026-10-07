import { expect, test } from '@playwright/test'
import { dayFromNow, loginAs, unique } from './helpers'

// One log per package, day and author: each project writes to its own package, and a day in the
// past that depends on the clock keeps a re-run against the same database from colliding.
const PACKAGE_INDEX: Record<string, number> = { mobile: 1, tablet: 2, desktop: 3 }
const pastDay = () => dayFromNow(-(1 + (Math.floor(Date.now() / 1000) % 700)))

test('the site engineer writes the daily log and sees it in the recent list', async ({ page }, info) => {
  const summary = unique(info, 'Lắp đặt thiết bị')
  await loginAs(page, 'onsite')
  await page.goto('/daily-log')

  await page.locator('#dl-package').selectOption({ index: PACKAGE_INDEX[info.project.name] })
  await page.locator('#dl-date').fill(pastDay())
  await page.getByRole('spinbutton', { name: 'Tiến độ hoàn thành (%)' }).fill('35')
  await page.getByLabel('Công việc đã làm').fill(summary)
  await page.getByLabel('Nhân lực (số người)').fill('8')
  await page.getByRole('button', { name: 'Gửi nhật ký' }).click()

  const queue = page.getByRole('region', { name: 'Đã ghi, đang gửi' })
  await expect(queue.getByText('Đã gửi')).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('region', { name: 'Nhật ký gần đây' })).toContainText(summary)
  await expect(page.getByLabel('Công việc đã làm')).toHaveValue('') // ready for the next entry
})
