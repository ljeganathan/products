export interface PlanMix {
  plan_code: string;
  plan_name: string;
  tenant_count: number;
}

export interface PlatformDashboard {
  active_tenant_count: number;
  trialing_count: number;
  churned_this_month_count: number;
  mrr_paise: number;
  plan_mix: PlanMix[];
  overdue_invoices_count: number;
}
