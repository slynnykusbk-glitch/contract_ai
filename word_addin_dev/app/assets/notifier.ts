const env = (() => {
  if (typeof process !== "undefined" && process.env?.NODE_ENV) {
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

function toast(msg: string, level: string) {
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

export function notifyOk(msg: string, ctx?: unknown) {
  toast(msg, "ok");
  try {
    if (isProd) {
      console.log("[OK]", msg);
    } else {
      console.log("[OK]", msg, ctx);
    }
  } catch {}
}

export function notifyErr(msg: string, err?: unknown) {
  toast(msg, "error");
  try {
    if (isProd) {
      console.error("[ERR]", msg);
    } else {
      console.error("[ERR]", msg, err);
    }
  } catch {}
}

export function notifyWarn(msg: string, ctx?: unknown) {
  toast(msg, "warn");
  try {
    if (isProd) {
      console.warn("[WARN]", msg);
    } else {
      console.warn("[WARN]", msg, ctx);
    }
  } catch {}
}
