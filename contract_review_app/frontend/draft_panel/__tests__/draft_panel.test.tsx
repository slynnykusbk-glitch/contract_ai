import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react-dom/test-utils';

vi.mock('../../common/http', () => ({
  postJSON: vi.fn(async () => ({ proposed_text: 'Hello from AI' })),
  getHealth: vi.fn(async () => ({})),
  ensureHeadersSet: vi.fn(),
}));

import { DraftAssistantPanel } from '../index';

describe('DraftAssistantPanel', () => {
  it('renders proposed draft text from API response', async () => {
    (globalThis as any).localStorage = { getItem: () => '', setItem: () => {} };
    (globalThis as any).navigator = { clipboard: { writeText: async (_: string) => {} } };
    (globalThis as any).Office = {
      context: {
        document: {
          setSelectedDataAsync: (_text: string, _opts: any, cb: any) => cb({ status: 'succeeded' }),
        },
      },
      CoercionType: { Text: 'text' },
      AsyncResultStatus: { Succeeded: 'succeeded' },
    };

    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(<DraftAssistantPanel initialAnalysis={{ cid: '1', text: 'clause' }} />);
    });

    const button = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Get AI Draft'),
    ) as HTMLButtonElement;

    await act(async () => {
      button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await act(async () => {});

    expect(container.textContent).toContain('Hello from AI');
  });
});
