import { describe, it, expect, afterEach } from 'vitest';
import { updateResultsTraceLink } from '../updateResultsTraceLink.ts';

function createStubEnvironment() {
  const elementsById = new Map<string, any>();

  const matches = (el: any, selector: string): boolean => {
    if (!el) return false;
    switch (selector) {
      case '.muted':
        return Boolean(el.classList?.contains('muted'));
      case '[data-role="trace-link"]':
        return el.dataset?.role === 'trace-link';
      case '#traceBadges':
        return el.id === 'traceBadges';
      case 'a[data-role="open-trace"]':
        return el.tagName === 'A' && el.dataset?.role === 'open-trace';
      default:
        return false;
    }
  };

  const querySelectorIn = (node: any, selector: string): any => {
    if (!node?.children) return null;
    for (const child of node.children) {
      if (matches(child, selector)) return child;
      const nested = querySelectorIn(child, selector);
      if (nested) return nested;
    }
    return null;
  };

  const registerId = (el: any) => {
    Object.defineProperty(el, 'id', {
      get() {
        return el._id || '';
      },
      set(value: string) {
        if (el._id) {
          elementsById.delete(el._id);
        }
        el._id = value;
        if (value) {
          elementsById.set(value, el);
        }
      },
      configurable: true,
      enumerable: true,
    });
  };

  const makeElement = (tag: string): any => {
    const element: any = {
      tagName: tag.toUpperCase(),
      children: [] as any[],
      dataset: {} as Record<string, string>,
      style: {} as Record<string, string>,
      parentNode: null,
      className: '',
      appendChild(child: any) {
        this.children.push(child);
        child.parentNode = this;
        return child;
      },
      querySelector(selector: string) {
        return querySelectorIn(this, selector);
      },
    };
    element.classList = {
      add(cls: string) {
        if (!element.className) {
          element.className = cls;
        } else if (!this.contains(cls)) {
          element.className += ` ${cls}`;
        }
      },
      remove(cls: string) {
        element.className = element.className
          .split(/\s+/)
          .filter(token => token && token !== cls)
          .join(' ');
      },
      contains(cls: string) {
        return element.className.split(/\s+/).includes(cls);
      },
    };
    Object.defineProperty(element, 'textContent', {
      get() {
        return element._textContent || '';
      },
      set(value: string) {
        element._textContent = value ?? '';
        element.children = [];
      },
      configurable: true,
      enumerable: true,
    });
    registerId(element);
    return element;
  };

  const root = makeElement('div');
  const resultsBlock = makeElement('div');
  resultsBlock.id = 'resultsBlock';
  const header = makeElement('div');
  header.classList.add('muted');
  resultsBlock.appendChild(header);
  root.appendChild(resultsBlock);

  const documentStub = {
    createElement: makeElement,
    getElementById(id: string) {
      return elementsById.get(id) ?? null;
    },
    querySelector(selector: string) {
      return querySelectorIn(root, selector);
    },
  } as any;

  return { documentStub, header };
}

const originalDocument = (globalThis as any).document;

describe('updateResultsTraceLink', () => {
  afterEach(() => {
    (globalThis as any).document = originalDocument;
  });

  it('shows trace link with cid', () => {
    const { documentStub, header } = createStubEnvironment();
    (globalThis as any).document = documentStub;

    updateResultsTraceLink('abc', 'https://backend.test');

    const container = header.querySelector('[data-role="trace-link"]');
    expect(container).toBeTruthy();
    expect(container?.style.display).toBe('');

    const link = container?.querySelector('a[data-role="open-trace"]');
    expect(link?.href).toBe('https://backend.test/api/trace/abc.html');
    expect(link?.textContent).toBe('Open TRACE');

    const badges = header.querySelector('#traceBadges');
    expect(badges).toBeTruthy();
    expect(badges?.style.display).toBe('none');
  });

  it('hides trace link when cid missing', () => {
    const { documentStub, header } = createStubEnvironment();
    (globalThis as any).document = documentStub;

    updateResultsTraceLink('', 'https://backend.test');

    const container = header.querySelector('[data-role="trace-link"]');
    expect(container?.style.display).toBe('none');

    const badges = header.querySelector('#traceBadges');
    expect(badges?.style.display).toBe('none');
  });
});
