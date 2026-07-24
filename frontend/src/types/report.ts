export interface SalesReportDay {
  bucket: string;
  total_paise: number;
  bill_count: number;
}

export interface SalesReport {
  date_from: string;
  date_to: string;
  range_clamped: boolean;
  total_paise: number;
  bill_count: number;
  avg_bill_paise: number;
  daily: SalesReportDay[];
}

export interface GstSummary {
  date_from: string;
  date_to: string;
  range_clamped: boolean;
  subtotal_paise: number;
  discount_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  total_paise: number;
  bill_count: number;
}
