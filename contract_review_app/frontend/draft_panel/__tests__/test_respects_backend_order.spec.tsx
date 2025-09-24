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

describe('DraftAssistantPanel respects backend order', () => {
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

  it('renders findings exactly in backend order', async () => {
    const analysis = {
      findings: [
        { rule_id: 'R3', code: 'R3', message: 'Third', severity: 'high' },
        { rule_id: 'R1', code: 'R1', message: 'First', severity: 'medium' },
        { rule_id: 'R2', code: 'R2', message: 'Second', severity: 'medium' },
      ],
    };

    const handle = await renderPanel(analysis);
    handles.push(handle);

    const section = getFindingsSection(handle.container);
    const cards = getFindingCards(section);
    const codes = cards.map((card) => card.querySelector('b')?.textContent);
    expect(codes).toEqual(['R3', 'R1', 'R2']);
  });
});
