import { afterEach, describe, expect, mock, test } from 'bun:test'

import { fetchReadings } from './synthhome'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

// Queue mock: each fetch call returns the next page (the last page repeats).
function mockFetchPages(pages: Array<{ items: unknown[]; count: number }>) {
  let call = 0
  globalThis.fetch = mock(() => {
    const body = pages[Math.min(call, pages.length - 1)]
    call += 1
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
  }) as unknown as typeof fetch
}

describe('fetchAllPages (via fetchReadings)', () => {
  test('returns all items from a single page', async () => {
    mockFetchPages([{ items: [{ metric: 'temp_f' }, { metric: 'humidity' }], count: 2 }])

    const result = await fetchReadings('tempest', 'temp_f')

    expect(result).toHaveLength(2)
  })

  test('pages through when count exceeds the first page (the truncation bug)', async () => {
    mockFetchPages([
      { items: Array.from({ length: 100 }, (_, i) => ({ i })), count: 150 },
      { items: Array.from({ length: 50 }, (_, i) => ({ i: 100 + i })), count: 150 },
    ])

    const result = await fetchReadings('tempest', 'temp_f')

    // Must return all 150 — not silently truncate to the first page of 100.
    expect(result).toHaveLength(150)
  })

  test('stops if a page returns no items, even when count disagrees', async () => {
    mockFetchPages([
      { items: Array.from({ length: 100 }, () => ({})), count: 999 },
      { items: [], count: 999 },
    ])

    const result = await fetchReadings('tempest', 'temp_f')

    // The empty-page guard prevents an infinite loop when count is wrong.
    expect(result).toHaveLength(100)
  })
})
