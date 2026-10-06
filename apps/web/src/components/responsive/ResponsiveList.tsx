import type { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  cell: (row: T) => ReactNode
  /** Hidden below `lg` to keep the md table readable. */
  secondary?: boolean
}

interface ResponsiveListProps<T> {
  rows: T[]
  rowKey: (row: T) => string
  columns: Column<T>[]
  /** Card for < md (SPEC 15.4: tables become cards on phones). */
  renderCard: (row: T) => ReactNode
  caption: string
}

export function ResponsiveList<T>({ rows, rowKey, columns, renderCard, caption }: ResponsiveListProps<T>) {
  return (
    <>
      <ul className="space-y-2 md:hidden" aria-label={caption}>
        {rows.map((row) => (
          <li key={rowKey(row)} className="rounded-md border border-border p-3">
            {renderCard(row)}
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={`px-3 py-2 font-medium ${c.secondary ? 'hidden lg:table-cell' : ''}`}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)} className="border-b border-border">
                {columns.map((c) => (
                  <td key={c.key} className={`px-3 py-2 ${c.secondary ? 'hidden lg:table-cell' : ''}`}>
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
