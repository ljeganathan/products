import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import { Switch } from "@/components/ui/Switch";
import {
  getOnlinePaymentSettings,
  type OnlinePaymentProvider,
  saveOnlinePaymentSettings,
  testOnlinePaymentConnection,
} from "@/modules/admin/onlinePaymentsApi";

const inputClass =
  "min-h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";

const PROVIDER_LABELS: Record<OnlinePaymentProvider, string> = {
  razorpay: "Razorpay",
  cashfree: "Cashfree",
};

function errorText(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  return fallback;
}

// Settings > Preferences card for a hotel's own online payment account. The hotel creates
// the account with its chosen provider (Razorpay or Cashfree) and pastes its keys here, so
// customer money goes straight to the hotel's bank and KOTMate never holds it. Only one
// provider takes payments at a time. Secrets are write-only.
export function OnlinePaymentsSettings() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["online-payment-settings"], queryFn: getOnlinePaymentSettings });

  const [selected, setSelected] = useState<OnlinePaymentProvider | null>(null);
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [environment, setEnvironment] = useState<"sandbox" | "production">("sandbox");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const current = data?.providers.find((p) => p.provider === selected) ?? null;

  // Start on whichever provider is taking payments (Razorpay when none is).
  useEffect(() => {
    if (data && selected === null) setSelected(data.provider);
  }, [data, selected]);

  // Switching provider shows that provider's saved details, not the previous one's.
  useEffect(() => {
    if (!current) return;
    setKeyId(current.key_id ?? "");
    setEnvironment(current.environment ?? "sandbox");
    setKeySecret("");
    setWebhookSecret("");
    setNotice(null);
    // Only when the selected provider changes, so an in-progress edit isn't overwritten by a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const save = useMutation({
    mutationFn: (enabled?: boolean) =>
      saveOnlinePaymentSettings({
        provider: selected ?? "razorpay",
        key_id: keyId || undefined,
        key_secret: keySecret || undefined,
        webhook_secret: selected === "razorpay" && webhookSecret ? webhookSecret : undefined,
        environment: selected === "cashfree" ? environment : undefined,
        enabled,
      }),
    onSuccess: (_, enabled) => {
      const label = PROVIDER_LABELS[selected ?? "razorpay"];
      setKeySecret("");
      setWebhookSecret("");
      setNotice({
        ok: true,
        text: enabled === undefined ? "Saved." : enabled ? `${label} enabled for online payments.` : "Online payments turned off.",
      });
      void queryClient.invalidateQueries({ queryKey: ["online-payment-settings"] });
    },
    onError: (err) => setNotice({ ok: false, text: errorText(err, "Couldn't save — please try again.") }),
  });

  const test = useMutation({
    mutationFn: () => testOnlinePaymentConnection(selected ?? "razorpay"),
    onSuccess: (res) =>
      setNotice({
        ok: true,
        text: `Connected to ${PROVIDER_LABELS[selected ?? "razorpay"]} (${res.is_test_mode ? "test" : "live"} mode).`,
      }),
    onError: (err) =>
      setNotice({ ok: false, text: errorText(err, `Couldn't connect to ${PROVIDER_LABELS[selected ?? "razorpay"]}.`) }),
  });

  async function copyWebhook() {
    if (!current) return;
    try {
      await navigator.clipboard.writeText(current.webhook_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — the URL is selectable text below */
    }
  }

  if (isLoading || !data || !data.available || !current || !selected) return null;

  const label = PROVIDER_LABELS[selected];
  const isCashfree = selected === "cashfree";

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Online payments</h3>
        {current.key_id && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
              current.is_test_mode ? "bg-gold-soft text-gold" : "bg-accent-soft text-accent"
            }`}
          >
            {current.is_test_mode ? "Test mode" : "Live"}
          </span>
        )}
        {current.enabled && (
          <span className="rounded-full bg-veg/15 px-2 py-0.5 text-[10px] font-bold uppercase text-veg">In use</span>
        )}
      </div>
      <p className="mb-3 text-xs text-foreground/60">
        Lets QR self-order customers pay on their phone. Money goes straight to your own {label} account. Only one
        provider takes payments at a time.
      </p>

      <div role="tablist" aria-label="Payment provider" className="mb-3 inline-flex rounded-md border border-border p-0.5">
        {(["razorpay", "cashfree"] as const).map((provider) => {
          const status = data.providers.find((p) => p.provider === provider);
          const active = provider === selected;
          return (
            <button
              key={provider}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setSelected(provider)}
              className={`min-h-9 rounded px-3 text-sm font-semibold ${
                active ? "bg-accent text-accent-foreground" : "text-foreground/70 hover:bg-accent/10"
              }`}
            >
              {PROVIDER_LABELS[provider]}
              {status?.enabled && <span className="ml-1.5 text-[10px] uppercase">· in use</span>}
            </button>
          );
        })}
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-foreground/70" htmlFor="pg-key-id">
            {isCashfree ? "Client ID" : "Key ID"}
          </label>
          <input
            id="pg-key-id"
            className={inputClass}
            value={keyId}
            placeholder={isCashfree ? "Your Cashfree client ID" : "rzp_test_… or rzp_live_…"}
            autoComplete="off"
            onChange={(e) => setKeyId(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-foreground/70" htmlFor="pg-key-secret">
            {isCashfree ? "Client secret" : "Key secret"} {current.has_secret && <span className="text-veg">· saved</span>}
          </label>
          <input
            id="pg-key-secret"
            type="password"
            className={inputClass}
            value={keySecret}
            placeholder={current.has_secret ? "Leave blank to keep the saved secret" : "Secret"}
            autoComplete="new-password"
            onChange={(e) => setKeySecret(e.target.value)}
          />
        </div>
        {isCashfree ? (
          <div className="flex flex-col gap-1 sm:col-span-2">
            <label className="text-xs font-medium text-foreground/70" htmlFor="pg-environment">
              Environment
            </label>
            <select
              id="pg-environment"
              className={inputClass}
              value={environment}
              onChange={(e) => setEnvironment(e.target.value as "sandbox" | "production")}
            >
              <option value="sandbox">Sandbox (test, no real money)</option>
              <option value="production">Production (live, real money)</option>
            </select>
          </div>
        ) : (
          <div className="flex flex-col gap-1 sm:col-span-2">
            <label className="text-xs font-medium text-foreground/70" htmlFor="pg-webhook-secret">
              Webhook secret (optional) {current.has_webhook_secret && <span className="text-veg">· saved</span>}
            </label>
            <input
              id="pg-webhook-secret"
              type="password"
              className={inputClass}
              value={webhookSecret}
              placeholder={current.has_webhook_secret ? "Leave blank to keep the saved secret" : "Webhook secret"}
              autoComplete="new-password"
              onChange={(e) => setWebhookSecret(e.target.value)}
            />
          </div>
        )}
      </div>

      <div className="mt-2.5 rounded-md bg-surface-2 p-2.5 text-xs">
        <p className="mb-1 font-medium">
          Webhook URL for your {label} dashboard ({isCashfree ? "Developers → Webhooks" : "Settings → Webhooks"})
        </p>
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 select-all break-all text-[11px]">{current.webhook_url}</code>
          <button
            type="button"
            onClick={() => void copyWebhook()}
            className="shrink-0 rounded-md border border-border px-2 py-1 font-semibold hover:bg-accent/10"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="mt-1 text-foreground/60">
          {isCashfree
            ? "Events: payment success and payment failed. Optional — payments are also confirmed directly with Cashfree, but the webhook makes confirmation faster and covers customers who close the page."
            : "Events: payment.captured, payment.failed, order.paid. Optional — payments are also confirmed directly with Razorpay, but the webhook makes confirmation faster and covers customers who close the page."}
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={save.isPending}
          onClick={() => save.mutate(undefined)}
          className="min-h-9 rounded-md bg-accent px-4 text-sm font-semibold text-accent-foreground disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : "Save keys"}
        </button>
        <button
          type="button"
          disabled={test.isPending || !current.has_secret}
          onClick={() => test.mutate()}
          className="min-h-9 rounded-md border border-border px-4 text-sm font-semibold hover:bg-accent/10 disabled:opacity-50"
        >
          {test.isPending ? "Checking…" : "Test connection"}
        </button>
        {notice && (
          <span role="status" className={`text-xs font-semibold ${notice.ok ? "text-veg" : "text-chili"}`}>
            {notice.text}
          </span>
        )}
      </div>

      <div className="mt-3 border-t border-border pt-3">
        <Switch
          checked={current.enabled}
          disabled={save.isPending || !current.configured}
          onChange={(next) => save.mutate(next)}
          label={`Accept online payments with ${label}`}
          description="Customers see a Pay button on the Bill tab. Turning this on switches off the other provider. Save and test your keys first."
        />
      </div>
    </div>
  );
}
