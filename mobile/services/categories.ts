import { api } from './api';
import { Category, TransactionType } from '../types';

export const categoryApi = {
  async getCategories(type?: TransactionType): Promise<Category[]> {
    const res = await api.get<Category[]>('/api/categories', {
      params: type ? { type } : undefined,
    });
    return res.data;
  },

  async addCategory(payload: {
    type: TransactionType;
    name: string;
    aliases?: string;
  }): Promise<Category> {
    const res = await api.post<Category>('/api/categories', payload);
    return res.data;
  },

  async deleteCategory(id: number): Promise<void> {
    await api.delete(`/api/categories/${id}`);
  },
};
