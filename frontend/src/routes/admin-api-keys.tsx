import { useTranslation } from "react-i18next";

export default function AdminAPIKeysPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$API_KEYS_TITLE", "API Keys")}
      </h3>
      <p className="text-tertiary">
        {t(
          "ADMIN$API_KEYS_DESCRIPTION",
          "Manage organization API keys for programmatic access.",
        )}
      </p>
    </div>
  );
}
