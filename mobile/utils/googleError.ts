/**
 * User-facing messages for native Google failures.
 *
 * Returns null when the error is not a Google-specific one, so the caller can
 * fall back to the normal API error description.
 */
export function describeGoogleError(error: unknown): string | null {
  const code = (error as { code?: string } | null)?.code;
  if (code === 'PLAY_SERVICES_NOT_AVAILABLE') {
    return 'Google Play Services tidak tersedia di perangkat ini.';
  }
  if (code === 'DEVELOPER_ERROR') {
    return 'Konfigurasi Google untuk aplikasi ini belum benar.';
  }
  if (error instanceof Error) {
    if (error.message === 'GOOGLE_UNAVAILABLE') {
      return 'Login Google tidak tersedia di build ini.';
    }
    if (error.message === 'GOOGLE_NO_ID_TOKEN') {
      return 'Google tidak mengirim token login. Coba lagi.';
    }
  }
  return null;
}