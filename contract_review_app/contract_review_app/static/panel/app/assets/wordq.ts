export type Job<T=any> = () => Promise<T> | T;
let chain: Promise<any> = Promise.resolve();
export const wordQ = {
  run<T>(job: Job<T>): Promise<T> {
    const next = chain.then(() => Promise.resolve().then(job));
    chain = next.catch(() => {});
    return next;
  }
};
(globalThis as any).wordQ = (globalThis as any).wordQ || wordQ;
export default wordQ;
