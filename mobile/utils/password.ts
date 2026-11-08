/**
 * Client-side validation for new passwords matching the backend bcrypt rules.
 *
 * Passwords must be at least 8 characters and at most 72 UTF-8 bytes.
 */

export function utf8ByteLength(value: string): number {
  if (typeof TextEncoder !== 'undefined') {
    return new TextEncoder().encode(value).length;
  }
  return unescape(encodeURIComponent(value)).length;
}

export function validateNewPassword(password: string): string | null {
  if (password.length < 8) {
    return 'Password must be at least 8 characters.';
  }
  if (utf8ByteLength(password) > 72) {
    return 'Password must be at most 72 UTF-8 bytes.';
  }
  return null;
}
