/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for API calls; defaults to the dev proxy at /api. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
