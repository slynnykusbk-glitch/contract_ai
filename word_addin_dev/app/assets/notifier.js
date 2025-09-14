const env = (() => {
  if (typeof process !== "undefined" && (process.env === null || process.env === void 0 ? void 0 : process.env.NODE_ENV)) {
    return process.env.NODE_ENV;
  }
  try {
    if (typeof localStorage !== "undefined") {
      return localStorage.getItem("NODE_ENV") || "";
    }
  } catch {}
  return "development";
})();
const isProd = env === "production";
function toast(msg, level) {
  try {
    const el = document.getElementById("console");
    if (!el) return;
    el.textContent = msg;
    el.setAttribute("data-level", level);
    setTimeout(() => {
      el.textContent = "";
      el.removeAttribute("data-level");
    }, 3000);
  } catch {}
}
function notifyOk(msg, ctx) {
  toast(msg, "ok");
  try {
    if (isProd) {
      console.log("[OK]", msg);
    } else {
      console.log("[OK]", msg, ctx);
    }
  } catch {}
}
function notifyErr(msg, err) {
  toast(msg, "error");
  try {
    if (isProd) {
      console.error("[ERR]", msg);
    } else {
      console.error("[ERR]", msg, err);
    }
  } catch {}
}
function notifyWarn(msg, ctx) {
  toast(msg, "warn");
  try {
    if (isProd) {
      console.warn("[WARN]", msg);
    } else {
      console.warn("[WARN]", msg, ctx);
    }
  } catch {}
}
export { notifyErr, notifyOk, notifyWarn };
