import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { formatINR } from "@/lib/utils";
import { listPlans, updatePlan, type Plan } from "@/modules/product-owner/platformApi";

function PlanCard({ plan }: { plan: Plan }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: plan.name,
    price_monthly: plan.price_monthly,
    price_yearly: plan.price_yearly,
    max_users: plan.max_users,
    max_locations: plan.max_locations,
    is_active: plan.is_active,
  });
  const [featuresText, setFeaturesText] = useState(JSON.stringify(plan.features, null, 2));
  const [featuresError, setFeaturesError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      let features: Record<string, boolean> | undefined;
      try {
        features = JSON.parse(featuresText);
        setFeaturesError(null);
      } catch {
        setFeaturesError("Features must be valid JSON.");
        throw new Error("invalid json");
      }
      return updatePlan(plan.id, { ...form, features });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wide">{plan.code}</h2>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          />
          Active
        </label>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium text-foreground/70">
          Display Name
          <input
            className="mt-1 min-h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs font-medium text-foreground/70">
            Price / month
            <input
              type="number"
              min={0}
              className="mt-1 min-h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={form.price_monthly}
              onChange={(e) => setForm((f) => ({ ...f, price_monthly: Number(e.target.value) }))}
            />
          </label>
          <label className="text-xs font-medium text-foreground/70">
            Price / year
            <input
              type="number"
              min={0}
              className="mt-1 min-h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={form.price_yearly}
              onChange={(e) => setForm((f) => ({ ...f, price_yearly: Number(e.target.value) }))}
            />
          </label>
          <label className="text-xs font-medium text-foreground/70">
            Max Users (blank = unlimited)
            <input
              type="number"
              min={0}
              className="mt-1 min-h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={form.max_users ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, max_users: e.target.value === "" ? null : Number(e.target.value) }))
              }
            />
          </label>
          <label className="text-xs font-medium text-foreground/70">
            Max Locations
            <input
              type="number"
              min={1}
              className="mt-1 min-h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={form.max_locations}
              onChange={(e) => setForm((f) => ({ ...f, max_locations: Number(e.target.value) }))}
            />
          </label>
        </div>

        <label className="text-xs font-medium text-foreground/70">
          Feature Flags (JSON)
          <textarea
            rows={8}
            className="mt-1 w-full rounded-md border border-border bg-background p-2 font-mono text-xs"
            value={featuresText}
            onChange={(e) => setFeaturesText(e.target.value)}
          />
        </label>
        {featuresError && <p className="text-xs text-chili">{featuresError}</p>}

        <p className="text-xs text-foreground/50">
          Current: {formatINR(plan.price_monthly)}/mo · {formatINR(plan.price_yearly)}/yr
        </p>

        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
          className="mt-1 self-start rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-accent-foreground disabled:opacity-60"
        >
          {mutation.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

export function PlansPage() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["plans"], queryFn: listPlans });

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Plans</h1>
      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load plans.</p>}
      {data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {data.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </div>
      )}
    </div>
  );
}
