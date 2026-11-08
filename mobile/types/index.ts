/**
 * TypeScript definitions for the Finance Mobile App.
 */

export type TransactionType = 'income' | 'expense' | 'investment';

export interface User {
  id: number;
  email?: string | null;
  first_name?: string | null;
  timezone: string;
  currency: string;
  created_at?: string;
  telegram_linked?: boolean;
  google_linked?: boolean;
  has_password?: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ForgotPasswordResponse {
  message: string;
  request_id: string;
  expires_in: number;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface Category {
  id: number;
  user_id: number;
  type: TransactionType;
  name: string;
  aliases: string;
  is_default: number;
}

export interface Transaction {
  id: number;
  user_id: number;
  type: TransactionType;
  category_id?: number | null;
  category_name?: string | null;
  amount: number;
  note?: string | null;
  asset_name?: string | null;
  transaction_date: string; // YYYY-MM-DD
}

export interface QuickInputPreview {
  type?: TransactionType | null;
  type_label?: string | null;
  category_name?: string | null;
  amount?: number | null;
  note?: string | null;
  asset_name?: string | null;
  transaction_date?: string | null;
  is_valid: boolean;
  error?: string | null;
}

export interface CategoryTotalItem {
  name: string;
  amount: number;
  percentage: number;
}

export interface PeriodReport {
  title: string;
  start_date: string;
  end_date: string;
  total_income: number;
  total_expense: number;
  total_investment: number;
  net: number;
  average_expense: number;
  investment_percentage: number;
  top_expense_categories: CategoryTotalItem[];
}

export interface CategoryBreakdown {
  title: string;
  type: string;
  categories: CategoryTotalItem[];
  total_amount: number;
}

export interface InvestmentReport {
  title: string;
  total_investment: number;
  investment_percentage: number;
  by_type: CategoryTotalItem[];
  by_asset: CategoryTotalItem[];
}

// --- Debt / Receivable Types ---

export type DebtType = 'debt' | 'receivable';
export type DebtStatus = 'active' | 'settled';

export interface Debt {
  id: number;
  user_id: number;
  type: DebtType;
  person_name: string;
  total_amount: number;
  paid_amount: number;
  note?: string | null;
  due_date?: string | null; // YYYY-MM-DD
  status: DebtStatus;
  cash_synced?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DebtPayment {
  id: number;
  debt_id: number;
  amount: number;
  note?: string | null;
  payment_date: string;
  created_at?: string | null;
}

export interface DebtSummary {
  total_debt_remaining: number;
  total_receivable_remaining: number;
  active_debt_count: number;
  active_receivable_count: number;
  due_soon_count: number;
}

// --- Recurring Transaction Types ---

export type RecurringFrequency = 'weekly' | 'monthly';

export interface RecurringTransaction {
  id: number;
  user_id: number;
  type: TransactionType;
  category_id?: number | null;
  category_name?: string | null;
  amount: number;
  note?: string | null;
  asset_name?: string | null;
  frequency: RecurringFrequency;
  day_of_week?: number | null; // 0 = Monday, 6 = Sunday
  day_of_month?: number | null;
  start_date: string; // YYYY-MM-DD
  next_run_date: string; // YYYY-MM-DD
  last_run_date?: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RecurringPayload {
  type: TransactionType;
  category_id?: number | null;
  category_name?: string;
  amount: number;
  note?: string;
  asset_name?: string;
  frequency: RecurringFrequency;
  day_of_week?: number | null;
  day_of_month?: number | null;
  start_date: string;
  is_active?: boolean;
}

