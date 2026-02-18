import { useTranslation } from "react-i18next";

export type ProvenanceTier = "org" | "team" | "personal";

interface SettingsProvenanceProps {
  tier: ProvenanceTier;
}

const TIER_STYLES: Record<ProvenanceTier, string> = {
  org: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  team: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  personal:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
};

const TIER_LABELS: Record<ProvenanceTier, string> = {
  org: "SETTINGS$PROVENANCE_ORG",
  team: "SETTINGS$PROVENANCE_TEAM",
  personal: "SETTINGS$PROVENANCE_PERSONAL",
};

const TIER_DEFAULTS: Record<ProvenanceTier, string> = {
  org: "Set at org level",
  team: "Overridden by team",
  personal: "Personal override",
};

export function SettingsProvenance({ tier }: SettingsProvenanceProps) {
  const { t } = useTranslation();

  return (
    <span
      className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full font-medium ${TIER_STYLES[tier]}`}
    >
      {t(TIER_LABELS[tier], TIER_DEFAULTS[tier])}
    </span>
  );
}
