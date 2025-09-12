function notifyOk(msg) {
  try {
    console.log("[OK]", msg);
  } catch {
  }
}
function notifyErr(msg) {
  try {
    console.error("[ERR]", msg);
  } catch {
  }
}
function notifyWarn(msg) {
  try {
    console.warn("[WARN]", msg);
  } catch {
  }
}
export {
  notifyErr,
  notifyOk,
  notifyWarn
};
