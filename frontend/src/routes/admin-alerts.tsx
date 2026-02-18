import { useTranslation } from "react-i18next";

export default function AdminAlertsPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$ALERTS_TITLE", "Alerts")}
      </h3>
      <p className="text-tertiary">
        {t(
          "ADMIN$ALERTS_DESCRIPTION",
          "Configure alert rules and notification channels.",
        )}
      </p>
    </div>
  );
}
