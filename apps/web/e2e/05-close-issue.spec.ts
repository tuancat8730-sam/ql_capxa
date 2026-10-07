import { expect, test } from '@playwright/test'
import { loginAs, unique } from './helpers'

test('an issue is reported, resolved with a result and then closed', async ({ page }, info) => {
  const title = unique(info, 'Mất điện tại xã')
  await loginAs(page, 'director')
  await page.goto('/issues')

  await page.getByRole('button', { name: 'Báo vướng mắc' }).click()
  const form = page.getByRole('dialog', { name: 'Báo vướng mắc' })
  await form.getByLabel('Tiêu đề').fill(title)
  await form.getByRole('button', { name: 'Lưu' }).click()
  await expect(form).toBeHidden()

  const card = page.getByRole('button', { name: new RegExp(title) }).first()
  await card.click()

  const detail = page.getByRole('dialog', { name: new RegExp(title) })
  await detail.getByRole('button', { name: 'Giải quyết' }).click()
  await detail.getByLabel('Kết quả xử lý').fill('Đã làm việc với điện lực, có điện trở lại')
  await detail.getByLabel('Quyết định của').fill('Giám đốc QLDA')
  await detail.getByRole('button', { name: 'Giải quyết' }).last().click()
  await expect(detail).toContainText('Đã giải quyết')
  await expect(detail.getByRole('region', { name: 'Lịch sử' })).toContainText('Giải quyết')

  await detail.getByRole('button', { name: 'Đóng vướng mắc' }).click()
  await expect(detail).toContainText('Đã đóng')
})
