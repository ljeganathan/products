import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";

import { Switch } from "@/components/ui/Switch";
import {
  getOnlinePaymentSettings,
  saveOnlinePaymentSettings,
  testOnlinePaymentConnection,
} from "@/modules/admin/onlinePaymentsApi";

const inputClass =
  "min-h-9 w-full rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";

function errorText(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  return fallback;
}

// Settings > Preferences card for a hotel's own Razorpay account (Model A: the hotel
// creates the Razorpay account and pastes its keys here, so customer money goes straight
// to the hotel's bank and KOTMate never holds it). Secrets are write-only.
export function OnlinePaymentsSettings() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["online-payment-settings"], queryFn: getOnlinePaymentSettings });

  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (data) setKeyId(data.key_id ?? "");
  }, [data]);

  const save = useMutation({
    mutationFn: (enabled?: boolean) =>
      saveOnlinePaymentSettings({
        key_id: keyId || undefined,
        key_secret: keySecret || undefined,
        webhook_secret: webhookSecret || undefined,
        enabled,
      }),
    onSuccess: (_, enabled) => {
      setKeySecret("");
      setWebhookSecret("");
      setNotice({ ok: true, text: enabled === undefined ? "Saved." : enabled ? "Online payments enabled." : "Online payments turned off." });
      void queryClient.invalidateQueries({ queryKey: ["online-payment-settings"] });
    },
    onError: (err) => setNotice({ ok: false, text: errorText(err, "Couldn't save — please try again.") }),
  });

  const test = useMutation({
    mutationFn: testOnlinePaymentConnection,
    onSuccess: (res) =>
      setNotice({ ok: true, text: `Connected to Razorpay (${res.is_test_mode ? "test" : "live"} mode).` }),
    onError: (err) => setNotice({ ok: false, text: errorText(err, "Couldn't connect to Razorpay.") }),
  });

  async function copyWebhook() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.webhook_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked — the URL is selectable text below */
    }
  }

  if (isLoading || !data || !data.available) return null;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Online payments (Razorpay)</h3>
        {data.key_id && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
              data.is_test_mode ? "bg-gold-soft text-gold" : "bg-accent-soft text-accent"
            }`}
          >
            {data.is_test_mode ? "Test mode" : "Live"}
          </span>
        )}
      </div>
      <p className="mb-3 text-xs text-foreground/60">
        Lets QR self-order customers pay on their phone (Google Pay and PhonePe open directly). Money goes straight
        to your own Razorpay account. Create one at razorpay.com, then paste its API keys here.
      </p>

      <div className="grid gap-2.5 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-foreground/70" htmlFor="rzp-key-id">
            Key ID
          </label>
          <input
            id="rzp-key-id"
            className={inputClass}
            value={keyId}
            placeholder="rzp_test_… or rzp_live_…"
            autoComplete="off"
            onChange={(e) => setKeyId(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-foreground/70" htmlFor="rzp-key-secret">
            Key secret {data.has_secret && <span className="text-veg">· saved</span>}
          </label>
          <input
            id="rzp-key-secret"
            type="password"
            className={inputClass}
            value={keySecret}
            placeholder={data.has_secret ? "Leave blank to keep the saved secret" : "Key secret"}
            autoComplete="new-password"
            onChange={(e) => setKeySecret(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1 sm:col-span-2">
          <label className="text-xs font-medium text-foreground/70" htmlFor="rzp-webhook-secret">
            Webhook secret (optional) {data.has_webhook_secret && <span className="text-veg">· saved</span>}
          </label>
          <input
            id="rzp-webhook-secret"
            type="password"
            className={inputClass}
            value={webhookSecret}
            placeholder={data.has_webhook_secret ? "Leave blank to keep the saved secret" : "Webhook secret"}
            autoComplete="new-password"
            onChange={(e) => setWebhookSecret(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-2.5 rounded-md bg-surface-2 p-2.5 text-xs">
        <p className="mb-1 font-medium">Webhook URL for your Razorpay dashboard (Settings → Webhooks)</p>
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 select-all break-all text-[11px]">{data.webhook_url}</code>
          <button
            type="button"
            onClick={() => void copyWebhook()}
            className="shrink-0 rounded-md border border-border px-2 py-1 font-semibold hover:bg-accent/10"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="mt-1 text-foreground/60">
          Events: payment.captured, payment.failed, order.paid. Optional — payments are also confirmed directly with
          Razorpay, but the webhook makes confirmation faster and covers customers who close the page.
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
          disabled={test.isPending || !data.has_secret}
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
          checked={data.enabled}
          disabled={save.isPending || !data.has_secret}
          onChange={(next) => save.mutate(next)}
          label="Accept online payments"
          description="Customers see a Pay button on the Bill tab. Save and test your keys first."
        />
      </div>
    </div>
  );
}
