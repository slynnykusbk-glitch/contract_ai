import { describe, it, expect } from 'vitest'
import { postJson } from './api-client'

describe('postJson', () => {
  it('throws when missing headers', async () => {
    ;(globalThis as any).document = { getElementById: () => ({ value: '' }) }
    ;(globalThis as any).localStorage = { getItem: () => '' }
    await expect(postJson('/x', {})).rejects.toThrow('MISSING_HEADERS')
  })

  it('sends headers when present', async () => {
    let captured: any = null
    ;(globalThis as any).document = { getElementById: () => ({ value: 'https://base' }) }
    ;(globalThis as any).localStorage = {
      getItem: (k: string) => (k === 'api_key' ? 'KEY' : k === 'schemaVersion' ? '1.2' : '')
    }
    ;(globalThis as any).fetch = async (url: string, opts: any) => {
      captured = opts
      return { status: 200 }
    }
    await postJson('/test', { a: 1 })
    expect(captured.headers['x-api-key']).toBe('KEY')
    expect(captured.headers['x-schema-version']).toBe('1.2')
  })
})
