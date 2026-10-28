import { api } from './api';
import {
  CategoryBreakdown,
  InvestmentReport,
  PeriodReport,
  TransactionType,
} from '../types';

export const reportApi = {
  async getDailyReport(date?: string): Promise<PeriodReport> {
    const res = await api.get<PeriodReport>('/api/reports/daily', {
      params: date ? { target_date: date } : undefined,
    });
    return res.data;
  },

  async getWeeklyReport(date?: string): Promise<PeriodReport> {
    const res = await api.get<PeriodReport>('/api/reports/weekly', {
      params: date ? { target_date: date } : undefined,
    });
    return res.data;
  },

  async getMonthlyReport(year?: number, month?: number): Promise<PeriodReport> {
    const res = await api.get<PeriodReport>('/api/reports/monthly', {
      params: { year, month },
    });
    return res.data;
  },

  async getCategoryBreakdown(params: {
    type?: TransactionType;
    start_date?: string;
    end_date?: string;
  }): Promise<CategoryBreakdown> {
    const res = await api.get<CategoryBreakdown>('/api/reports/category-breakdown', {
      params,
    });
    return res.data;
  },

  async getInvestmentReport(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<InvestmentReport> {
    const res = await api.get<InvestmentReport>('/api/reports/investment', {
      params,
    });
    return res.data;
  },
};
