import { describe, it, expect } from 'vitest'

function createElementFactory(elements: Record<string, any>) {
  return function createElement(tag: string) {
    const el: any = {
      tagName: tag.toUpperCase(),
      children: [] as any[],
      style: {},
      appendChild(child: any) {
        if (child === undefined || child === null) {
          return child
        }
        this.children.push(child)
        if (typeof child === 'object') {
          child.parentElement = this
        }
        return child
      },
      removeChild(child: any) {
        this.children = this.children.filter((node: any) => node !== child)
        if (child && typeof child === 'object') {
          child.parentElement = null
        }
        return child
      },
      setAttribute(name: string, value: any) {
        ;(this as any)[name] = value
      },
    }

    let textContent = ''
    Object.defineProperty(el, 'textContent', {
      get() {
        return textContent
      },
      set(val) {
        textContent = String(val ?? '')
      },
    })

    Object.defineProperty(el, 'innerHTML', {
      get() {
        return textContent
      },
      set(_val) {
        textContent = ''
        el.children = []
      },
    })

    Object.defineProperty(el, 'id', {
      get() {
        return (this as any)._id
      },
      set(val) {
        ;(this as any)._id = val
        if (val) {
          elements[val] = el
        }
      },
    })

    return el
  }
}

function collectText(node: any): string {
  if (!node) return ''
  let text = node.textContent || ''
  if (Array.isArray(node.children) && node.children.length) {
    for (const child of node.children) {
      text += collectText(child)
    }
  }
  return text
}

function findAnchor(node: any): any {
  if (!node) return undefined
  if (node.tagName === 'A') return node
  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      const found = findAnchor(child)
      if (found) return found
    }
  }
  return undefined
}

describe('Companies House rendering', () => {
  it('renders Companies House block with verdict and links', async () => {
    const elements: Record<string, any> = {
      clauseTypeOut: { textContent: '' },
      resFindingsCount: { textContent: '' },
      visibleHiddenOut: { textContent: '' },
      findingsList: { innerHTML: '', children: [] as any[], appendChild(el: any) { this.children.push(el); return el } },
      recommendationsList: { innerHTML: '', children: [] as any[], appendChild(el: any) { this.children.push(el); return el } },
      findingsBlock: { style: { display: 'none' } },
      recommendationsBlock: { style: { display: 'none' } },
    }

    const createElement = createElementFactory(elements)
    const resultsBlock = createElement('div')
    resultsBlock.style.display = 'none'
    resultsBlock.style.removeProperty = function (prop: string) {
      delete (this as any)[prop]
    }
    resultsBlock.id = 'resultsBlock'

    const docStub: any = {
      getElementById(id: string) {
        return elements[id] || null
      },
      createElement,
    }
    elements.resultsBlock = resultsBlock

    const originalDocument = (globalThis as any).document
    const originalWindow = (globalThis as any).window
    const originalLocalStorage = (globalThis as any).localStorage
    const originalTesting = (globalThis as any).__CAI_TESTING__

    try {
      ;(globalThis as any).document = docStub
      ;(globalThis as any).window = globalThis as any
      ;(globalThis as any).localStorage = { getItem: () => null, setItem: () => {} }
      ;(globalThis as any).__CAI_TESTING__ = true

      const mod = await import('../assets/taskpane')

      const payload = {
        summary: {
          clause_type: 'NDA',
          parties: [
            {
              registry: {
                name: 'ACME LTD',
                number_or_duns: '12345678',
                status: 'active',
                address: '1 Main Street',
                sic_codes: ['62020'],
              },
            },
          ],
        },
        findings: [],
        recommendations: [],
        meta: {
          companies_meta: [
            {
              verdict: 'match',
              from_document: { name: 'ACME LTD', number: '12345678' },
              matched: {
                company_name: 'ACME LIMITED',
                company_number: '12345678',
                company_status: 'active',
                address_snippet: '1 MAIN STREET, LONDON',
                sic_codes: ['62020'],
                links: {
                  self: 'https://api.company-information.service.gov.uk/company/12345678',
                  officers: 'https://api.company-information.service.gov.uk/company/12345678/officers',
                },
              },
            },
          ],
        },
      }

      mod.renderAnalysisSummary(payload)

      const chBlock = elements.companiesHouseBlock
      expect(chBlock).toBeTruthy()
      expect(resultsBlock.children.includes(chBlock)).toBe(true)

      const entry = chBlock.children[1]
      expect(entry).toBeTruthy()
      const header = entry.children[0]
      expect(header.children[0].textContent).toBe('Match')

      const text = collectText(chBlock)
      expect(text).toContain('Company number: 12345678')
      expect(text).toContain('Status: active')

      const link = findAnchor(chBlock)
      expect(link?.href).toContain('/company/12345678')
    } finally {
      if (originalDocument === undefined) {
        delete (globalThis as any).document
      } else {
        ;(globalThis as any).document = originalDocument
      }
      if (originalWindow === undefined) {
        delete (globalThis as any).window
      } else {
        ;(globalThis as any).window = originalWindow
      }
      if (originalLocalStorage === undefined) {
        delete (globalThis as any).localStorage
      } else {
        ;(globalThis as any).localStorage = originalLocalStorage
      }
      if (originalTesting === undefined) {
        delete (globalThis as any).__CAI_TESTING__
      } else {
        ;(globalThis as any).__CAI_TESTING__ = originalTesting
      }
    }
  })
})
