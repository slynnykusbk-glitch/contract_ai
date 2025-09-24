import React from 'react';
import { createRoot } from 'react-dom/client';
import type { Root } from 'react-dom/client';
import { act } from 'react-dom/test-utils';

vi.mock('../../common/http', () => ({
  postJSON: vi.fn(async () => ({ draft_text: '' })),
  getHealth: vi.fn(async () => ({})),
  ensureHeadersSet: vi.fn(),
}));

import { DraftAssistantPanel } from '../index';

interface RenderHandle {
  container: HTMLDivElement;
  root: Root;
}

function getFindingsSection(container: HTMLElement): HTMLElement {
  const heading = Array.from(container.querySelectorAll('h3')).find(
    (el) => el.textContent?.trim() === 'Findings',
  );
  if (!heading || !heading.parentElement) {
    throw new Error('Findings section not found');
  }
  return heading.parentElement;
}

function getFindingCards(section: HTMLElement): HTMLElement[] {
  const heading = section.querySelector('h3');
  return Array.from(section.children).filter((node): node is HTMLElement => {
    if (!(node instanceof HTMLElement)) return false;
    if (heading && node === heading) return false;
    if (node.tagName !== 'DIV') return false;
    return true;
  });
}

async function renderPanel(analysis: any): Promise<RenderHandle> {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<DraftAssistantPanel initialAnalysis={analysis} initialAnalysisMeta={{}} />);
  });
  return { container, root };
}

describe('DraftAssistantPanel load more preserves order', () => {
  let handles: RenderHandle[] = [];

  beforeEach(() => {
    handles = [];
    (globalThis as any).localStorage = { getItem: () => '', setItem: () => {} };
    (globalThis as any).sessionStorage = { getItem: () => null, setItem: () => {} };
    (globalThis as any).navigator = { clipboard: { writeText: async () => {} } };
    (globalThis as any).Office = {
      context: {
        document: {
          setSelectedDataAsync: (_text: string, _opts: any, cb: any) => cb({ status: 'succeeded' }),
        },
      },
      CoercionType: { Text: 'text' },
      AsyncResultStatus: { Succeeded: 'succeeded' },
    };
  });

  afterEach(async () => {
    await Promise.all(
      handles.splice(0).map(async ({ root, container }) => {
        await act(async () => {
          root.unmount();
        });
        container.remove();
      }),
    );
  });

  it('shows all findings in backend order after loading more', async () => {
    const findings = Array.from({ length: 150 }, (_v, idx) => ({
      rule_id: `R${idx + 1}`,
      code: `R${idx + 1}`,
      message: `Finding ${idx + 1}`,
    }));
    const analysis = { findings };

    const handle = await renderPanel(analysis);
    handles.push(handle);

    const section = getFindingsSection(handle.container);
    let cards = getFindingCards(section);
    expect(cards).toHaveLength(100);
    let codes = cards.map((card) => card.querySelector('b')?.textContent);
    expect(codes).toEqual(findings.slice(0, 100).map((f) => f.code));

    const loadMoreButton = Array.from(section.querySelectorAll('button')).find(
      (btn) => btn.textContent === 'Load more',
    );
    expect(loadMoreButton).toBeTruthy();

    await act(async () => {
      loadMoreButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await act(async () => {});

    cards = getFindingCards(section);
    expect(cards).toHaveLength(150);
    codes = cards.map((card) => card.querySelector('b')?.textContent);
    expect(codes).toEqual(findings.map((f) => f.code));
  });
});
