import axios from "axios";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";

import { login } from "@/modules/auth/authApi";
import { roleHomePath, useAuthStore } from "@/modules/auth/authStore";

export function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const accessToken = useAuthStore((state) => state.accessToken);
  const role = useAuthStore((state) => state.role);
  const setSession = useAuthStore((state) => state.setSession);

  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in — no reason to show the form again.
  if (accessToken && role) {
    return <Navigate to={roleHomePath(role)} replace />;
  }

  const toggleLanguage = () => {
    void i18n.changeLanguage(i18n.language === "en" ? "ta" : "en");
  };

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tokens = await login(userId, password);
      setSession({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        role: tokens.role,
        tenantId: tokens.tenant_id,
        loginId: tokens.login_id,
      });
      navigate(roleHomePath(tokens.role), { replace: true });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError(t("auth.invalidCredentials"));
      } else {
        setError(t("auth.genericError"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen w-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-lg border border-border shadow-sm">
        {/* Colorful branding band (CLAUDE.md §9 — dense/colorful, not muted-gray SaaS) */}
        <div className="bg-gradient-to-r from-gold via-accent to-chili px-6 py-8 text-center text-accent-foreground">
          <h1 className="text-2xl font-bold">{t("app.name")}</h1>
          <p className="mt-1 text-sm opacity-90">{t("app.tagline")}</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-6 py-6">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="user_id" className="text-sm font-medium">
              {t("auth.userId")}
            </label>
            <input
              id="user_id"
              name="user_id"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="min-h-11 rounded-md border border-border bg-background px-3 text-base outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              {t("auth.password")}
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="min-h-11 rounded-md border border-border bg-background px-3 text-base outline-none focus:ring-2 focus:ring-accent"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 min-h-11 rounded-md bg-accent px-4 font-semibold text-accent-foreground disabled:opacity-60"
          >
            {submitting ? t("auth.signingIn") : t("auth.signIn")}
          </button>

          <button
            type="button"
            onClick={toggleLanguage}
            data-testid="lang-toggle"
            className="self-center rounded-full border border-border px-3 py-1 text-xs font-semibold hover:bg-accent/10"
          >
            {i18n.language === "en" ? "EN / தமிழ்" : "தமிழ் / EN"}
          </button>
        </form>
      </div>
    </div>
  );
}
