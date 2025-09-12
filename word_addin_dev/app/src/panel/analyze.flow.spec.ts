import { describe, it, expect, vi } from 'vitest'
import { postJson } from './api-client'

describe('analyze flow', () => {
  it('sends only text payload', async () => {
    let captured: any = null
    ;(globalThis as any).document = { getElementById: () => ({ value: 'https://base' }) }
    ;(globalThis as any).localStorage = {
      getItem: (k: string) => (k === 'api_key' ? 'KEY' : k === 'schema_version' ? '1.2' : '')
    }
    ;(globalThis as any).fetch = async (url: string, opts: any) => {
      captured = opts
      return { status: 200 }
    }
    await postJson('/api/analyze', { text: 'hello' })
    const body = JSON.parse(captured.body)
    expect(body).toEqual({ text: 'hello' })
    expect(body).not.toHaveProperty('mode')
  })
})

describe('dev bootstrap', () => {
  it('auto sets headers and enables analyze', async () => {
    vi.resetModules()
    const store: Record<string, string> = {}
    ;(globalThis as any).localStorage = {
      getItem: (k: string) => store[k] || '',
      setItem: (k: string, v: string) => { store[k] = v }
    }
    const analyzeBtn = { disabled: true }
    ;(globalThis as any).document = {
      getElementById: (id: string) => {
        if (id === 'backendUrl') return { value: 'https://base' }
        if (id === 'btnAnalyze') return analyzeBtn
        return null
      },
      querySelector: (sel: string) => (sel === '#btnAnalyze' ? analyzeBtn : null)
    }
    ;(globalThis as any).location = { hostname: 'localhost' }
    ;(globalThis as any).fetch = async (url: string) => {
      if (url === 'https://base/health') {
        return {
          json: async () => ({ status: 'ok', schema: '1.5' }),
          headers: { get: (h: string) => (h === 'x-schema-version' ? '1.5' : null) }
        } as any
      }
      return { status: 200, json: async () => ({}) } as any
    }
    ;(globalThis as any).Word = { run: async (fn: any) => fn({ document: { body: { load: () => {}, text: '' }, getSelection: () => ({ load: () => {}, text: '' }) }, sync: async () => {} }) }
    ;(globalThis as any).Office = { onReady: () => Promise.resolve() };

    (globalThis as any).__CAI_TESTING__ = true;
    const mod = await import('./index')
    await mod.startPanel()

    expect(store['api_key']).toBe('local-test-key-123')
    expect(store['schema_version']).toBe('1.4')
    expect(analyzeBtn.disabled).toBe(false)
  })
})
