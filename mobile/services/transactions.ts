import { api } from './api';
import { QuickInputPreview, Transaction, TransactionType } from '../types';

export const transactionApi = {
  async getTransactions(params?: {
    start_date?: string;
    end_date?: string;
    type?: TransactionType;
    limit?: number;
    offset?: number;
  }): Promise<Transaction[]> {
    const res = await api.get<Transaction[]>('/api/transactions', { params });
    return res.data;
  },

  async getTransaction(id: number): Promise<Transaction> {
    const res = await api.get<Transaction>(`/api/transactions/${id}`);
    return res.data;
  },

  async createTransaction(payload: {
    type: TransactionType;
    amount: number;
    category_name?: string;
    category_id?: number;
    note?: string;
    asset_name?: string;
    transaction_date: string;
  }): Promise<Transaction> {
    const res = await api.post<Transaction>('/api/transactions', payload);
    return res.data;
  },

  async updateTransaction(
    id: number,
    payload: {
      amount?: number;
      category_id?: number;
      note?: string;
      asset_name?: string;
      transaction_date?: string;
    }
  ): Promise<Transaction> {
    const res = await api.put<Transaction>(`/api/transactions/${id}`, payload);
    return res.data;
  },

  async deleteTransaction(id: number): Promise<void> {
    await api.delete(`/api/transactions/${id}`);
  },

  async previewQuickInput(text: string, referenceDate?: string): Promise<QuickInputPreview> {
    const res = await api.post<QuickInputPreview>('/api/transactions/quick-input', {
      text,
      reference_date: referenceDate,
    });
    return res.data;
  },

  async confirmQuickInput(text: string, referenceDate?: string): Promise<Transaction> {
    const res = await api.post<Transaction>('/api/transactions/quick-input/confirm', {
      text,
      reference_date: referenceDate,
    });
    return res.data;
  },
};
