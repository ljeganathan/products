export type PlanCode = "lite" | "pro" | "pro_max";

export interface Plan {
  id: string;
  code: PlanCode;
  name: string;
  price_paise: number;
  max_users: number;
  max_stores: number;
  max_printer_profiles: number;
  low_stock_alerts: boolean;
  saved_bill_days: number;
  features_json: Record<string, boolean>;
  is_active: boolean;
}

export interface PlanCreate {
  code: PlanCode;
  name: string;
  price_paise: number;
  max_users: number;
  max_stores: number;
  max_printer_profiles: number;
  low_stock_alerts?: boolean;
  saved_bill_days: number;
  features_json?: Record<string, boolean>;
  is_active?: boolean;
}

export type PlanUpdate = Partial<PlanCreate>;
