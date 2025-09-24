import { describe, it, expect, afterEach } from 'vitest';
import { renderTraceBadges } from '../traceBadges.ts';

function createBadgesEnvironment() {
  const elementsById = new Map<string, any>();

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
      appendChild(child: any) {
        this.children.push(child);
        child.parentNode = this;
        return child;
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
  const badges = makeElement('span');
  badges.id = 'traceBadges';
  root.appendChild(badges);

  const documentStub = {
    createElement: makeElement,
    getElementById(id: string) {
      return elementsById.get(id) ?? null;
    },
  } as any;

  return { documentStub, badges };
}

const originalDocument = (globalThis as any).document;
const originalCache = (globalThis as any).__traceCache;

describe('renderTraceBadges degrade modes', () => {
  afterEach(() => {
    (globalThis as any).document = originalDocument;
    (globalThis as any).__traceCache = originalCache;
  });

  it('keeps badges hidden when trace is missing', () => {
    const { documentStub, badges } = createBadgesEnvironment();
    (globalThis as any).document = documentStub;
    (globalThis as any).__traceCache = new Map<string, any>();

    renderTraceBadges('cid2');

    expect(badges.style.display).toBe('none');
    expect(badges.children).toHaveLength(0);
  });
});
