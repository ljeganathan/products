import { api } from "@/lib/api";

export async function updateCategoryDisplaySetting(
  showTamilCategories: boolean,
): Promise<{ show_tamil_categories: boolean }> {
  return (
    await api.patch<{ show_tamil_categories: boolean }>("/api/v1/settings/category-display", {
      show_tamil_categories: showTamilCategories,
    })
  ).data;
}
