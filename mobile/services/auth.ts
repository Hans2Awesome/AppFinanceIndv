import { api, setAuthToken } from './api';
import { AuthResponse, User } from '../types';

export const authApi = {
  async register(params: {
    email: string;
    password: string;
    first_name?: string;
  }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/register', params);
    setAuthToken(res.data.access_token);
    return res.data;
  },

  async login(params: { email: string; password: string }): Promise<AuthResponse> {
    const res = await api.post<AuthResponse>('/api/auth/login', params);
    setAuthToken(res.data.access_token);
    return res.data;
  },

  async getProfile(): Promise<User> {
    const res = await api.get<User>('/api/auth/me');
    return res.data;
  },

  logout() {
    setAuthToken(null);
  },
};
