import type { LucideIcon } from "lucide-react";
import { Clock } from "lucide-react";
import { useTranslation } from "react-i18next";

import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

export interface ComingSoonPageProps {
  titleKey: string;
  descriptionKey: string;
  icon?: LucideIcon;
}

/** Screens this phase wires into routing + RBAC but whose real feature
 * work lands in a later phase (per CLAUDE.md §6's phase plan). The route,
 * guard, and layout around it are fully functional now. */
export function ComingSoonPage({ titleKey, descriptionKey, icon }: ComingSoonPageProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t(titleKey)} />
      <EmptyState icon={icon ?? Clock} title={t("common.comingSoon")} description={t(descriptionKey)} />
    </div>
  );
}
