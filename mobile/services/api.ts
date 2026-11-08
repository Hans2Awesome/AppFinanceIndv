/**
 * Axios client with bearer auth and a single-flight refresh flow.
 *
 * The API base URL comes from EXPO_PUBLIC_API_URL at build time. There is no
 * fallback to a hardcoded host: a missing value fails fast instead of shipping
 * a dead tunnel URL to devices.
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
} from './session';

const configuredBaseUrl = process.env.EXPO_PUBLIC_API_URL;

if (!configuredBaseUrl) {
  throw new Error(
    'EXPO_PUBLIC_API_URL is not set. Copy mobile/.env.example to mobile/.env and point it at the API.'
  );
}

export const API_BASE_URL = configuredBaseUrl.replace(/\/+$/, '');

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const token = getRefreshToken();
  if (!token) {
    return false;
  }

  if (!refreshPromise) {
    refreshPromise = axios
      .post(
        `${API_BASE_URL}/api/auth/refresh`,
        { refresh_token: token },
        { timeout: 15000, headers: { 'Content-Type': 'application/json' } }
      )
      .then(async (response) => {
        await saveSession(response.data);
        return true;
      })
      .catch(async () => {
        await clearSession();
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    // A rejected password or Google proof is not an expired app session. Retrying
    // those requests would consume the guess budget twice and could sign out a
    // valid user when no refresh token is available.
    const credentialAction = /^\/api\/auth\/(login|register|google(?:\/link)?|change-password|account|forgot-password|reset-password)\/?$/.test(
      config?.url ?? ''
    );
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    const sessionFailure =
      detail === 'Token tidak valid atau sudah kedaluwarsa.' ||
      detail === 'Token sudah tidak berlaku. Silakan login kembali.';

    if (
      error.response?.status === 401 && config && !config._retry &&
      (!credentialAction || sessionFailure)
    ) {
      config._retry = true;
      if (await refreshSession()) {
        return api.request(config);
      }
    }

    return Promise.reject(error);
  }
);
