import { describe, it, expect } from 'vitest';

function matchesSelector(el: any, selector: string): boolean {
  if (!el) return false;
  if (selector === '.muted') {
    const cls = typeof el.className === 'string' ? el.className : '';
    return cls.split(/\s+/).includes('muted');
  }
  const roleMatch = selector.match(/^\[data-role="(.+)"\]$/);
  if (roleMatch) {
    return el.dataset?.role === roleMatch[1];
  }
  return false;
}

function createElementFactory(elements: Record<string, any>) {
  return function createElement(tag: string) {
    const el: any = {
      tagName: tag.toUpperCase(),
      children: [] as any[],
      style: {},
      dataset: {},
      className: '',
      parentElement: null as any,
      appendChild(child: any) {
        if (child === undefined || child === null) {
          return child;
        }
        if (typeof child === 'string') {
          const textNode = { nodeType: 3, textContent: String(child) };
          this.children.push(textNode);
          return textNode;
        }
        this.children.push(child);
        if (typeof child === 'object') {
          child.parentElement = this;
        }
        return child;
      },
      removeChild(child: any) {
        this.children = this.children.filter((node: any) => node !== child);
        if (child && typeof child === 'object') {
          child.parentElement = null;
        }
        return child;
      },
      append(...nodes: any[]) {
        for (const node of nodes) {
          if (node === undefined || node === null) continue;
          if (typeof node === 'string') {
            const textNode = { nodeType: 3, textContent: String(node) };
            this.children.push(textNode);
            continue;
          }
          this.appendChild(node);
        }
      },
      replaceChildren(...nodes: any[]) {
        this.children = [];
        this.append(...nodes);
      },
      querySelector(selector: string) {
        if (matchesSelector(this, selector)) {
          return this;
        }
        for (const child of this.children) {
          if (child && typeof child === 'object' && typeof child.querySelector === 'function') {
            const found = child.querySelector(selector);
            if (found) return found;
          }
        }
        return null;
      },
      setAttribute(name: string, value: any) {
        (this as any)[name] = value;
      },
      addEventListener() {
        // noop for tests
      },
    };

    let textContent = '';
    Object.defineProperty(el, 'textContent', {
      get() {
        if (textContent) return textContent;
        let acc = '';
        for (const child of el.children) {
          if (child && typeof child === 'object') {
            acc += child.textContent || '';
          } else if (typeof child === 'string') {
            acc += child;
          }
        }
        return acc;
      },
      set(val) {
        textContent = String(val ?? '');
        el.children = [];
      },
    });

    Object.defineProperty(el, 'innerHTML', {
      get() {
        return textContent;
      },
      set() {
        textContent = '';
        el.children = [];
      },
    });

    Object.defineProperty(el, 'id', {
      get() {
        return (this as any)._id;
      },
      set(val) {
        (this as any)._id = val;
        if (val) {
          elements[val] = el;
        }
      },
    });

    return el;
  };
}

function findAnchor(node: any): any {
  if (!node) return null;
  if (node.tagName === 'A') return node;
  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      const found = findAnchor(child);
      if (found) return found;
    }
  }
  return null;
}

describe('renderResults trace link', () => {
  it('renders trace link when cid is provided', async () => {
    const elements: Record<string, any> = {};
    const createElement = createElementFactory(elements);

    const clauseTypeOut = createElement('span');
    clauseTypeOut.dataset.role = 'clause-type';
    elements.resClauseType = clauseTypeOut;

    const findingsList = createElement('ol');
    findingsList.dataset.role = 'findings';
    elements.findingsList = findingsList;

    const findingsBlock = createElement('div');
    findingsBlock.id = 'findingsBlock';
    findingsBlock.style = { display: 'none' };
    elements.findingsBlock = findingsBlock;

    const recommendationsList = createElement('ol');
    recommendationsList.dataset.role = 'recommendations';
    elements.recommendationsList = recommendationsList;

    const recommendationsBlock = createElement('div');
    recommendationsBlock.id = 'recommendationsBlock';
    recommendationsBlock.style = { display: 'none' };
    elements.recommendationsBlock = recommendationsBlock;

    const findingsCount = createElement('span');
    findingsCount.dataset.role = 'findings-count';
    elements.resFindingsCount = findingsCount;

    const rawJson = createElement('pre');
    rawJson.dataset.role = 'raw-json';
    elements.rawJson = rawJson;

    const resultsBlock = createElement('section');
    resultsBlock.id = 'resultsBlock';
    const header = createElement('div');
    header.className = 'muted';
    header.textContent = 'Results';
    resultsBlock.appendChild(header);
    elements.resultsBlock = resultsBlock;

    const roleMap: Record<string, any> = {
      'clause-type': clauseTypeOut,
      findings: findingsList,
      'findings-count': findingsCount,
      'raw-json': rawJson,
      recommendations: recommendationsList,
    };

    const originalDocument = (globalThis as any).document;
    const originalWindow = (globalThis as any).window;
    const originalLocalStorage = (globalThis as any).localStorage;
    const originalTesting = (globalThis as any).__CAI_TESTING__;

    try {
      (globalThis as any).document = {
        getElementById(id: string) {
          return elements[id] || null;
        },
        querySelector(selector: string) {
          const roleMatch = selector.match(/^\[data-role="(.+)"\]$/);
          if (roleMatch) {
            return roleMap[roleMatch[1]] || null;
          }
          return null;
        },
        createElement,
      } as any;
      (globalThis as any).window = globalThis as any;
      (globalThis as any).localStorage = {
        getItem(key: string) {
          if (key === 'backend.url' || key === 'backendUrl') {
            return 'https://backend.test';
          }
          return null;
        },
        setItem() {},
      };
      (globalThis as any).__CAI_TESTING__ = true;

      const mod = await import('../assets/taskpane');
      mod.renderResults({
        meta: { cid: 'cid-123' },
        findings: [],
        recommendations: [],
      });

      const traceContainer = header.querySelector('[data-role="trace-link"]');
      expect(traceContainer).toBeTruthy();
      expect(traceContainer?.style.display).toBe('');

      const anchor = findAnchor(traceContainer);
      expect(anchor).toBeTruthy();
      expect(anchor?.href).toBe('https://backend.test/api/trace/cid-123');
      expect(anchor?.textContent).toBe('/api/trace/cid-123');
    } finally {
      if (originalDocument === undefined) {
        delete (globalThis as any).document;
      } else {
        (globalThis as any).document = originalDocument;
      }
      if (originalWindow === undefined) {
        delete (globalThis as any).window;
      } else {
        (globalThis as any).window = originalWindow;
      }
      if (originalLocalStorage === undefined) {
        delete (globalThis as any).localStorage;
      } else {
        (globalThis as any).localStorage = originalLocalStorage;
      }
      if (originalTesting === undefined) {
        delete (globalThis as any).__CAI_TESTING__;
      } else {
        (globalThis as any).__CAI_TESTING__ = originalTesting;
      }
    }
  });
});
