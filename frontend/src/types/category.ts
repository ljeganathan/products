export interface Category {
  id: string;
  tenant_id: string;
  name_en: string;
  name_ta: string;
  parent_category_id: string | null;
  hsn_code: string | null;
}

export interface CategoryCreate {
  name_en: string;
  name_ta: string;
  parent_category_id?: string | null;
  hsn_code?: string | null;
}

export type CategoryUpdate = Partial<CategoryCreate>;
