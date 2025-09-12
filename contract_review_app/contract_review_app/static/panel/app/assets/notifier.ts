export function notifyOk(msg: string)   { try { console.log("[OK]", msg); } catch {} }
export function notifyErr(msg: string)  { try { console.error("[ERR]", msg); } catch {} }
export function notifyWarn(msg: string) { try { console.warn("[WARN]", msg); } catch {} }
