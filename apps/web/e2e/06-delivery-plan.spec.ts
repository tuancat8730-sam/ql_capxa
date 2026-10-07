import { expect, test } from '@playwright/test'
import path from 'node:path'
import { loginAs } from './helpers'

// Package 04 of the seed. Replacing a plan keeps the tracking of unchanged steps (a feature), so each
// project first removes the plan the previous run left, and the order of the runs does not matter.
test('upload a delivery plan, read it in the tab, track a step', async ({ page }) => {
  await loginAs(page, 'director')
  await page.goto('/packages')
  await page.getByRole('link', { name: /Gói 04/ }).first().click()
  await page.getByRole('tab', { name: 'Kế hoạch' }).click()

  const remove = page.getByRole('button', { name: 'Xóa kế hoạch' })
  const empty = page.getByText('Gói thầu này chưa có kế hoạch triển khai.')
  await expect(remove.or(empty)).toBeVisible() // wait until the tab has loaded, then branch
  if (await remove.isVisible()) {
    page.once('dialog', (d) => void d.accept())
    await remove.click()
    await expect(empty).toBeVisible()
  }

  // a synthetic .docx with the layout of a real plan (made by apps/api/tests/plan_docs.py)
  await page.getByRole('button', { name: /Tải (kế hoạch|bản mới)/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Tải kế hoạch triển khai' })
  await dialog.getByLabel('Chọn tệp kế hoạch').setInputFiles(path.join(import.meta.dirname, 'fixtures', 'ke-hoach-mau.docx'))
  await dialog.getByRole('button', { name: 'Kiểm tra tệp' }).click()
  await expect(dialog.getByText(/hạng mục \(tổng 9\), 5 bước/)).toBeVisible({ timeout: 20_000 })
  await dialog.getByRole('button', { name: 'Lưu kế hoạch' }).click()
  await expect(dialog).toBeHidden()

  await expect(page.getByRole('region', { name: 'Giai đoạn 1' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Thiết bị theo hợp đồng' })).toContainText('2 hạng mục, tổng 9')
  await expect(page.getByRole('region', { name: 'Cần lưu ý' })).toContainText('kết thúc sau ngày kết thúc hợp đồng')

  await expect(page.getByText('Đã xong 0/5 bước (0%)')).toBeVisible()
  await page.getByRole('button', { name: 'Đánh dấu hoàn thành: 1' }).click()
  await expect(page.getByText('Đã xong 1/5 bước (20%)')).toBeVisible()
})
