import { describe, it, expect } from 'vitest'
import { postJson } from './api-client'

describe('analyze flow', () => {
  it('sends only text payload', async () => {
    let captured: any = null
    ;(globalThis as any).document = { getElementById: () => ({ value: 'https://base' }) }
    ;(globalThis as any).localStorage = {
      getItem: (k: string) => (k === 'api_key' ? 'KEY' : k === 'schemaVersion' ? '1.2' : '')
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
