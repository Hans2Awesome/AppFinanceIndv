import { AxiosError } from 'axios';
import { api } from './api';
import { clearSession, saveSession } from './session';
import { AuthResponse, User } from '../types';

export const authApi = {
  async register(params: {
    email: string;
    password: string;
    first_name?: string;
  }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/register', params);
    await saveSession(res.data);
    return res.data;
  },

  async login(params: { email: string; password: string }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/login', params);
    await saveSession(res.data);
    return res.data;
  },

  async getProfile(): Promise<User> {
    const res = await api.get<User>('/api/auth/me');
    return res.data;
  },

  async logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout');
    } catch {
      // The token may already be expired; clearing local state is enough.
    }
    await clearSession();
  },
};

/** Extract a human-readable message from an API error without leaking internals. */
export function describeApiError(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{ detail?: string | { msg?: string }[] }>;
  const detail = axiosError.response?.data?.detail;

  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) {
    return detail[0].msg;
  }
  if (axiosError.response?.status === 429) {
    return 'Terlalu banyak percobaan. Coba lagi nanti.';
  }
  if (!axiosError.response) {
    return 'Tidak dapat terhubung ke server. Periksa koneksi internet.';
  }
  return fallback;
}