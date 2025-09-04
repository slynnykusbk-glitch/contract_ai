export type Level = 'info' | 'warn' | 'error' | 'ok';

function target() {
  return document.getElementById('console') || null;
}

function emit(msg: string, level: Level = 'info') {
  const el = target();
  const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
  if (el) {
    el.textContent = line;
    el.setAttribute('data-level', level);
  } else {
    // в Word WebView alert запрещён — никогда не используем
    console[(level === 'error' ? 'error' : 'log')](line);
  }
}

export const notify = {
  info: (m: string) => emit(m, 'info'),
  ok:   (m: string) => emit(m, 'ok'),
  warn: (m: string) => emit(m, 'warn'),
  error:(m: string) => emit(m, 'error'),
};
