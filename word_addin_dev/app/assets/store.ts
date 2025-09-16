const DEFAULT_API_KEY = "";
export const DEFAULT_SCHEMA = "1.4";
const ADD_COMMENTS_KEY = "cai-comment-on-analyze";

function ensureDefaults(): void {
  try {
    if (localStorage.getItem("api_key") === null) {
      localStorage.setItem("api_key", DEFAULT_API_KEY);
    }
    if (localStorage.getItem("schema_version") === null) {
      localStorage.setItem("schema_version", DEFAULT_SCHEMA);
    }
    if (localStorage.getItem(ADD_COMMENTS_KEY) === null) {
      localStorage.setItem(ADD_COMMENTS_KEY, "1");
    }
  } catch {
    // ignore
  }
}

ensureDefaults();

export function getApiKeyFromStore(): string {
  try {
    return localStorage.getItem("api_key") || DEFAULT_API_KEY;
  } catch {
    return DEFAULT_API_KEY;
  }
}

export function setApiKey(k: string): void {
  try {
    localStorage.setItem("api_key", k);
  } catch {
    // ignore
  }
}

export function getSchemaFromStore(): string {
  try {
    return localStorage.getItem("schema_version") || DEFAULT_SCHEMA;
  } catch {
    return DEFAULT_SCHEMA;
  }
}

export function setSchemaVersion(v: string): void {
  try {
    localStorage.setItem("schema_version", v);
  } catch {
    // ignore
  }
}

export function getAddCommentsFlag(): boolean {
  try {
    const v = localStorage.getItem(ADD_COMMENTS_KEY);
    if (v === null) {
      localStorage.setItem(ADD_COMMENTS_KEY, "1");
      return true;
    }
    return v !== "0";
  } catch {
    return true;
  }
}

export function setAddCommentsFlag(v: boolean): void {
  try {
    localStorage.setItem(ADD_COMMENTS_KEY, v ? "1" : "0");
  } catch {
    // ignore
  }
}

// expose minimal CAI.Store for legacy consumers
const root: any = typeof globalThis !== "undefined" ? (globalThis as any) : (window as any);
root.CAI = root.CAI || {};
root.CAI.Store = root.CAI.Store || {};
root.CAI.Store.setApiKey = setApiKey;
root.CAI.Store.setSchemaVersion = setSchemaVersion;
root.CAI.Store.get = () => ({ apiKey: getApiKeyFromStore(), schemaVersion: getSchemaFromStore() });
root.CAI.Store.DEFAULT_BASE = root.CAI.Store.DEFAULT_BASE || "https://127.0.0.1:9443";
