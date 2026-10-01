import { api } from './api';
import { Debt, DebtPayment, DebtSummary, DebtType, DebtStatus } from '../types';

export const debtApi = {
  async getDebts(params?: {
    type?: DebtType;
    status?: DebtStatus;
    limit?: number;
    offset?: number;
  }): Promise<Debt[]> {
    const res = await api.get<Debt[]>('/api/debts', { params });
    return res.data;
  },

  async getDebt(id: number): Promise<Debt> {
    const res = await api.get<Debt>(`/api/debts/${id}`);
    return res.data;
  },

  async getSummary(): Promise<DebtSummary> {
    const res = await api.get<DebtSummary>('/api/debts/summary');
    return res.data;
  },

  async createDebt(payload: {
    type: DebtType;
    person_name: string;
    total_amount: number;
    note?: string;
    due_date?: string;
  }): Promise<Debt> {
    const res = await api.post<Debt>('/api/debts', payload);
    return res.data;
  },

  async updateDebt(
    id: number,
    payload: {
      person_name?: string;
      total_amount?: number;
      note?: string;
      due_date?: string;
      status?: DebtStatus;
    }
  ): Promise<Debt> {
    const res = await api.put<Debt>(`/api/debts/${id}`, payload);
    return res.data;
  },

  async deleteDebt(id: number): Promise<void> {
    await api.delete(`/api/debts/${id}`);
  },

  async addPayment(
    debtId: number,
    payload: {
      amount: number;
      note?: string;
      payment_date: string;
    }
  ): Promise<DebtPayment> {
    const res = await api.post<DebtPayment>(`/api/debts/${debtId}/payments`, payload);
    return res.data;
  },

  async getPayments(debtId: number): Promise<DebtPayment[]> {
    const res = await api.get<DebtPayment[]>(`/api/debts/${debtId}/payments`);
    return res.data;
  },
};
