import { describe, it, expect } from 'vitest'

describe('renderAnalysisSummary', () => {
  it('handles minimal response', async () => {
    const elements: Record<string, any> = {
      clauseTypeOut: { textContent: '' },
      visibleHiddenOut: { textContent: '' },
      findingsList: { innerHTML: '', children: [] as any[], appendChild(el: any){ this.children.push(el) } },
      recommendationsList: { innerHTML: '', children: [] as any[], appendChild(el: any){ this.children.push(el) } },
      findingsBlock: { style: { display: 'none' } },
      recommendationsBlock: { style: { display: 'none' } },
      resultsBlock: { style: { display: 'none', removeProperty(prop: string){ delete (this as any)[prop] } } }
    }
    ;(globalThis as any).document = {
      getElementById(id: string){ return elements[id] || null },
      createElement(){ return { textContent: '' } as any }
    } as any
    ;(globalThis as any).window = globalThis as any
    ;(globalThis as any).localStorage = { getItem: () => null, setItem: () => {} }
    ;(globalThis as any).__CAI_TESTING__ = true
    const mod = await import('../assets/taskpane')
    mod.renderAnalysisSummary({ findings: [], recommendations: [] })
    expect(elements.clauseTypeOut.textContent).toBe('—')
    expect(elements.visibleHiddenOut.textContent).toBe('0 / 0')
    expect(elements.findingsList.children.length).toBe(0)
    expect(elements.recommendationsList.children.length).toBe(0)
    expect(elements.resultsBlock.style.display).toBeUndefined()
  })

  it('ignores non-array findings', async () => {
    const elements: Record<string, any> = {
      clauseTypeOut: { textContent: '' },
      visibleHiddenOut: { textContent: '' },
      findingsList: { innerHTML: '', children: [] as any[], appendChild(el: any){ this.children.push(el) } },
      recommendationsList: { innerHTML: '', children: [] as any[], appendChild(el: any){ this.children.push(el) } },
      findingsBlock: { style: { display: 'none' } },
      recommendationsBlock: { style: { display: 'none' } },
      resultsBlock: { style: { display: 'none', removeProperty(prop: string){ delete (this as any)[prop] } } }
    }
    ;(globalThis as any).document = {
      getElementById(id: string){ return elements[id] || null },
      createElement(){ return { textContent: '' } as any }
    } as any
    ;(globalThis as any).window = globalThis as any
    ;(globalThis as any).localStorage = { getItem: () => null, setItem: () => {} }
    ;(globalThis as any).__CAI_TESTING__ = true
    const mod = await import('../assets/taskpane')
    expect(() => mod.renderAnalysisSummary({ findings: 'bad' as any })).not.toThrow()
    expect(elements.findingsList.children.length).toBe(0)
  })
})
