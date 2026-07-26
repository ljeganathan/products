/** Resolves which item name to show — Tamil when the tenant's
 * show_tamil_item_names setting is on (regardless of UI language), English
 * otherwise. Falls back to English if no Tamil name is available. */
export function resolveItemName(
  nameEn: string,
  nameTa: string | null | undefined,
  showTamil: boolean,
): string {
  return showTamil && nameTa ? nameTa : nameEn;
}
