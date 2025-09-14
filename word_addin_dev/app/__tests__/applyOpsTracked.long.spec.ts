import { describe, it, expect, vi } from 'vitest'

;(globalThis as any).window = globalThis
;(globalThis as any).document = { readyState: 'complete', addEventListener: vi.fn() }
;(globalThis as any).Office = { onReady: vi.fn() }

vi.mock('../assets/pending.ts', async () => {
  const actual = await vi.importActual('../assets/pending.ts')
  return { ...actual, withBusy: async (fn: any) => await fn() }
})

vi.mock('../assets/annotate.ts', async () => {
  const actual = await vi.importActual('../assets/annotate.ts')
  return { ...actual, COMMENT_PREFIX: '[CAI]', safeInsertComment: vi.fn() }
})

const innerRange: any = {}
innerRange.insertText = vi.fn().mockReturnValue(innerRange)
innerRange.getRange = vi.fn().mockReturnThis()
innerRange.search = vi.fn().mockReturnValue({ items: [innerRange], load: vi.fn() })
const innerCollection = { items: [innerRange], load: vi.fn() }
const fullSearch = vi.fn().mockReturnValue(innerCollection)

vi.mock('../assets/safeBodySearch.ts', () => ({
  safeBodySearch: vi.fn().mockResolvedValue({ items: [{ search: fullSearch }] })
}))


describe('applyOpsTracked long replacements', () => {
  it('clamps snippet before searching full range', async () => {
    const longText = 'x'.repeat(500)
    ;(globalThis as any).__lastAnalyzed = longText

    const run = vi.fn(async (cb: any) => {
      await cb({ document: { body: {} }, sync: vi.fn() })
    })
    ;(globalThis as any).Word = { run }

    const mod = await import('../assets/taskpane.ts')
    await mod.applyOpsTracked([{ start: 0, end: 500, replacement: 'R', context_before: 'a' }])

      expect(fullSearch).toHaveBeenCalledTimes(2)
      expect(fullSearch.mock.calls[0][0]).toBe(longText.slice(0, 240))
      expect(fullSearch.mock.calls[1][0]).toBe(longText.slice(-240))
    })
  })
