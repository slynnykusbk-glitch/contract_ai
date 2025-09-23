import '@testing-library/jest-dom/vitest';

type OfficeStub = {
  context: {
    requirements: { isSetSupported: () => boolean };
    document: { mode: string };
  };
};

const officeMock: OfficeStub = {
  context: { requirements: { isSetSupported: () => true }, document: { mode: 'edit' } },
};

(globalThis as typeof globalThis & { Office?: OfficeStub }).Office = officeMock;
