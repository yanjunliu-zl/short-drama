/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_API_TIMEOUT: string
  readonly VITE_ENABLE_ANALYTICS: string
  readonly VITE_ENABLE_DEBUG: string
  readonly VITE_ENABLE_MOCK_API: string
  readonly VITE_APP_NAME: string
  readonly VITE_APP_VERSION: string
  readonly VITE_APP_DESCRIPTION: string
  readonly VITE_DEV_PROXY_TARGET: string
  readonly VITE_DEV_SERVER_PORT: string
  readonly VITE_DEV_SERVER_HOST: string
  readonly VITE_BUILD_SOURCEMAP: string
  readonly VITE_BUILD_MINIFY: string
  readonly VITE_BUILD_TARGET: string
  readonly VITE_CSRF_ENABLED: string
  readonly VITE_CSP_ENABLED: string
  readonly VITE_MAX_UPLOAD_SIZE: string
  readonly VITE_ALLOWED_FILE_TYPES: string
  readonly VITE_MAX_VIDEO_DURATION: string
  readonly VITE_SUPPORTED_VIDEO_FORMATS: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}