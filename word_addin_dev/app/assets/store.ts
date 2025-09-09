const DEFAULT_API_KEY = "";
export const DEFAULT_SCHEMA = "1.4";

function ensureDefaults(): void {
  try {
    if (localStorage.getItem("api_key") === null) {
      localStorage.setItem("api_key", DEFAULT_API_KEY);
    }
    if (localStorage.getItem("schemaVersion") === null) {
      localStorage.setItem("schemaVersion", DEFAULT_SCHEMA);
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
    return localStorage.getItem("schemaVersion") || DEFAULT_SCHEMA;
  } catch {
    return DEFAULT_SCHEMA;
  }
}

export function setSchemaVersion(v: string): void {
  try {
    localStorage.setItem("schemaVersion", v);
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
root.CAI.Store.DEFAULT_BASE = root.CAI.Store.DEFAULT_BASE || "https://localhost:9443";
