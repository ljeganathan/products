import { isAxiosError } from "axios";
import { Store } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { login } from "@/api/auth";
import { LanguageToggle } from "@/components/LanguageToggle";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { roleHomePath } from "@/routes/roleHome";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const errors: typeof fieldErrors = {};
    if (!email.trim()) errors.email = t("auth.emailRequired");
    if (!password) errors.password = t("auth.passwordRequired");
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsSubmitting(true);
    try {
      const tokens = await login(email.trim(), password);
      setSession(tokens);
      void i18n.changeLanguage(tokens.user.language_pref);

      const from = (location.state as { from?: Location } | null)?.from;
      const destination = from ? `${from.pathname}${from.search}` : roleHomePath(tokens.user.role);
      navigate(destination, { replace: true });
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) {
        setFormError(t("auth.loginError"));
      } else {
        setFormError(t("auth.genericError"));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-teal-50 px-4">
      <div className="absolute right-4 top-4">
        <LanguageToggle />
      </div>

      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-card-hover">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Store className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="font-display text-xl font-semibold text-slate-900">{t("app.name")}</h1>
            <p className="mt-1 text-sm text-slate-500">{t("auth.loginSubtitle")}</p>
          </div>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 flex flex-col gap-4" noValidate>
          <Input
            type="email"
            autoComplete="email"
            label={t("auth.email")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldErrors.email}
          />
          <Input
            type="password"
            autoComplete="current-password"
            label={t("auth.password")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
          />

          {formError && (
            <p role="alert" className="text-sm text-danger-600">
              {formError}
            </p>
          )}

          <Button type="submit" size="lg" isLoading={isSubmitting} className="mt-2 w-full">
            {t("auth.loginButton")}
          </Button>
        </form>
      </div>
    </div>
  );
}
