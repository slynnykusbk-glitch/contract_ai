import { describe, it, expect } from 'vitest';
import { wordQ } from '../assets/wordq';

const delay = (ms: number) => new Promise(res => setTimeout(res, ms));

describe('wordQ', () => {
  it('runs jobs sequentially', async () => {
    const order: string[] = [];
    const job = (label: string, ms: number) => wordQ.run(async () => {
      order.push('start-' + label);
      await delay(ms);
      order.push('end-' + label);
    });
    const p1 = job('a', 20);
    const p2 = job('b', 10);
    const p3 = job('c', 0);
    await Promise.all([p1, p2, p3]);
    expect(order).toEqual([
      'start-a','end-a','start-b','end-b','start-c','end-c'
    ]);
  });
});
