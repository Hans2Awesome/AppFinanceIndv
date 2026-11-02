import { api } from './api';
import { RecurringPayload, RecurringTransaction } from '../types';

export const recurringApi = {
  async getRecurring(params?: { active_only?: boolean }): Promise<RecurringTransaction[]> {
    const res = await api.get<RecurringTransaction[]>('/api/recurring', { params });
    return res.data;
  },

  async createRecurring(payload: RecurringPayload): Promise<RecurringTransaction> {
    const res = await api.post<RecurringTransaction>('/api/recurring', payload);
    return res.data;
  },

  async updateRecurring(
    id: number,
    payload: Partial<RecurringPayload>
  ): Promise<RecurringTransaction> {
    const res = await api.put<RecurringTransaction>(`/api/recurring/${id}`, payload);
    return res.data;
  },

  async deleteRecurring(id: number): Promise<void> {
    await api.delete(`/api/recurring/${id}`);
  },
};