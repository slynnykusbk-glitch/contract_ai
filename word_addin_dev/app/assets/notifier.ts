export function notifyOk(msg: string)  { try { console.log("[OK]", msg); } catch {} }
export function notifyErr(msg: string) { try { console.error("[ERR]", msg); } catch {} }
