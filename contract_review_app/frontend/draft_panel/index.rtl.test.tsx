import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

const meta = { rules_evaluated: 1, rules_triggered: 0 };

jest.mock('../common/http', () => ({
  postJSON: jest.fn(),
  getHealth: jest.fn().mockResolvedValue(meta),
  ensureHeadersSet: jest.fn(),
}));

import { DraftAssistantPanel } from './index';

test('renders placeholder when findings is null', async () => {
  const analysis = { findings: null };
  const { container } = render(
    <DraftAssistantPanel initialAnalysis={analysis} initialMeta={meta} />
  );
  await screen.findByText(
    'No findings (rules_evaluated: 1, triggered: 0)'
  );
  expect(screen.queryByText(/^Error:/)).toBeNull();
  expect({ analysis, meta }).toMatchSnapshot();
});
