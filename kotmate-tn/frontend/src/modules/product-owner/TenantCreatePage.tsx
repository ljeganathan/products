import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { INDIAN_STATES } from "@/lib/constants";
import { createTenant, type TenantCreatePayload } from "@/modules/product-owner/platformApi";

const initialForm: TenantCreatePayload = {
  company_name: "",
  email: "",
  phone: "",
  door_no: "",
  street: "",
  city: "",
  district: "",
  state: "Tamil Nadu",
  pincode: "",
  plan_code: "lite",
  billing_cycle: "monthly",
  location_name: "",
  admin_local_handle: "",
  admin_name: "",
  admin_password: "",
};

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

export function TenantCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: TenantCreatePayload) => createTenant(payload),
    onSuccess: async (tenant) => {
      await queryClient.invalidateQueries({ queryKey: ["tenants"] });
      navigate(`/platform/tenants/${tenant.id}`);
    },
    onError: (err) => {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setError(String(err.response.data.detail));
      } else {
        setError("Failed to create tenant.");
      }
    },
  });

  function update<K extends keyof TenantCreatePayload>(key: K, value: TenantCreatePayload[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate(form);
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-4 text-xl font-bold">New Tenant</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">Company Master</legend>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Company Name</label>
            <input
              required
              className={inputClass}
              value={form.company_name}
              onChange={(e) => update("company_name", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Email</label>
              <input
                type="email"
                className={inputClass}
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Phone</label>
              <input
                type="tel"
                className={inputClass}
                value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Door No.</label>
              <input
                className={inputClass}
                value={form.door_no}
                onChange={(e) => update("door_no", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Street / Area</label>
              <input
                className={inputClass}
                value={form.street}
                onChange={(e) => update("street", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>City</label>
              <input
                className={inputClass}
                value={form.city}
                onChange={(e) => update("city", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>District</label>
              <input
                className={inputClass}
                value={form.district}
                onChange={(e) => update("district", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>State</label>
              <select
                className={inputClass}
                value={form.state}
                onChange={(e) => update("state", e.target.value)}
              >
                {INDIAN_STATES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>PIN Code</label>
              <input
                required
                pattern="[1-9][0-9]{5}"
                className={inputClass}
                value={form.pincode}
                onChange={(e) => update("pincode", e.target.value)}
              />
            </div>
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">Subscription</legend>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Plan</label>
              <select
                className={inputClass}
                value={form.plan_code}
                onChange={(e) => update("plan_code", e.target.value)}
              >
                <option value="lite">Lite</option>
                <option value="pro">Pro</option>
                <option value="pro_max">Pro Max</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Billing Cycle</label>
              <select
                className={inputClass}
                value={form.billing_cycle}
                onChange={(e) => update("billing_cycle", e.target.value)}
              >
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">First Location</legend>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Location Name</label>
            <input
              required
              placeholder="e.g. Main Branch"
              className={inputClass}
              value={form.location_name}
              onChange={(e) => update("location_name", e.target.value)}
            />
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">Tenant Admin</legend>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Local Login Handle</label>
              <input
                required
                placeholder="e.g. admin01"
                pattern="[A-Za-z0-9_-]+"
                className={inputClass}
                value={form.admin_local_handle}
                onChange={(e) => update("admin_local_handle", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Name</label>
              <input
                required
                className={inputClass}
                value={form.admin_name}
                onChange={(e) => update("admin_name", e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Password</label>
            <input
              required
              minLength={8}
              type="password"
              className={inputClass}
              value={form.admin_password}
              onChange={(e) => update("admin_password", e.target.value)}
            />
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="self-start rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          {mutation.isPending ? "Creating…" : "Create Tenant"}
        </button>
      </form>
    </div>
  );
}
