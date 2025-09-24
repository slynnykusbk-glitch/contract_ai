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

describe('DraftAssistantPanel main list dedupe guard', () => {
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

  it('renders duplicate findings when backend sends them', async () => {
    const analysis = {
      findings: [
        {
          rule_id: 'R1',
          code: 'R1',
          message: 'First occurrence',
          severity: 'medium',
          anchor: { start: 5, end: 10 },
        },
        {
          rule_id: 'R1',
          code: 'R1',
          message: 'Second occurrence',
          severity: 'high',
          anchor: { start: 5, end: 10 },
        },
      ],
    };

    const handle = await renderPanel(analysis);
    handles.push(handle);

    const section = getFindingsSection(handle.container);
    const cards = getFindingCards(section);
    expect(cards).toHaveLength(2);
    const messages = cards.map((card) => card.querySelectorAll('div')[1]?.textContent?.trim());
    expect(messages).toEqual(['First occurrence', 'Second occurrence']);
  });
});
