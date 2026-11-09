import { AxiosError } from 'axios';
import { api } from './api';
import { signOutGoogle } from './googleAuth';
import { clearSession, saveSession } from './session';
import { resetAppLockAfterSignIn } from './appLock';
import {
  AuthResponse,
  ForgotPasswordResponse,
  ResetPasswordResponse,
  User,
} from '../types';

export const authApi = {
  async register(params: {
    email: string;
    password: string;
    first_name?: string;
  }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/register', params);
    await resetAppLockAfterSignIn();
    await saveSession(res.data);
    return res.data;
  },

  async login(params: { email: string; password: string }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/login', params);
    await resetAppLockAfterSignIn();
    await saveSession(res.data);
    return res.data;
  },

  async getProfile(): Promise<User> {
    const res = await api.get<User>('/api/auth/me');
    return res.data;
  },

  async googleLogin(params: { idToken: string }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/google', {
      id_token: params.idToken,
    });
    await resetAppLockAfterSignIn();
    await saveSession(res.data);
    return res.data;
  },

  async linkGoogle(params: { idToken: string; password: string }): Promise<User> {
    const res = await api.post<User>('/api/auth/google/link', {
      id_token: params.idToken,
      password: params.password,
    });
    return res.data;
  },

  async changePassword(params: {
    current_password: string;
    new_password: string;
  }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/change-password', params);
    await saveSession(res.data);
    return res.data;
  },

  async forgotPassword(params: { email: string }): Promise<ForgotPasswordResponse> {
    const res = await api.post<ForgotPasswordResponse>('/api/auth/forgot-password', params);
    return res.data;
  },

  async resetPassword(params: {
    request_id: string;
    code: string;
    new_password: string;
  }): Promise<ResetPasswordResponse> {
    const res = await api.post<ResetPasswordResponse>('/api/auth/reset-password', params);
    return res.data;
  },

  async deleteAccount(params: {
    confirmation: 'DELETE';
    password?: string;
    id_token?: string;
  }): Promise<void> {
    await api.delete('/api/auth/account', { data: params });
    await signOutGoogle();
    await clearSession();
  },

  async createTelegramLinkToken(): Promise<{ code: string; expires_in_minutes: number }> {
    const res = await api.post<{ code: string; expires_in_minutes: number }>(
      '/api/auth/telegram-link-token'
    );
    return res.data;
  },

  async unlinkTelegram(): Promise<void> {
    await api.delete('/api/auth/telegram-link');
  },

  async logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout');
    } catch {
      // The token may already be expired; clearing local state is enough.
    }
    await signOutGoogle();
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
