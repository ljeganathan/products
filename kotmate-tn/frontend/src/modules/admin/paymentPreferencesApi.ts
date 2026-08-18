import { api } from "@/lib/api";

export async function updateDefaultPaymentMethod(
  method: "upi" | "cash" | "card",
): Promise<{ default_payment_method: string }> {
  return (
    await api.patch<{ default_payment_method: string }>("/api/v1/settings/default-payment-method", {
      default_payment_method: method,
    })
  ).data;
}
