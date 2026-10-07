import { expect, test } from '@playwright/test'
import { loginAs, unique } from './helpers'

test('a file goes straight to S3 and then shows up in the document list and in search', async ({ page }, info) => {
  const title = unique(info, 'Biên bản e2e')
  await loginAs(page, 'technical')
  await page.goto('/documents')
  await page.getByRole('button', { name: 'Tải lên' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Tải lên' })

  // a unique body so the duplicate check (same checksum in one package) never fires across runs
  await dialog.getByLabel('Chọn tệp').setInputFiles({
    name: 'bien-ban.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from(`%PDF-1.4\n% ${title}\n%%EOF`),
  })
  await dialog.getByLabel('Tiêu đề').fill(title)
  await dialog.getByRole('button', { name: 'Bắt đầu tải lên' }).click()
  await expect(dialog.getByText('✓')).toBeVisible({ timeout: 20_000 })
  await dialog.getByRole('button', { name: 'Đóng' }).last().click()

  // the list renders a card and a table variant; only one of them is visible per screen size
  await expect(page.getByText(title).filter({ visible: true }).first()).toBeVisible()

  // global search finds it without accents (Ctrl+K dialog)
  await page.getByRole('button', { name: 'Tìm kiếm' }).click()
  const search = page.getByRole('dialog', { name: 'Tìm kiếm' })
  await search.getByRole('searchbox').fill('bien ban e2e')
  await expect(search.getByRole('region', { name: 'Tài liệu' }).getByText(title).first()).toBeVisible()
})
