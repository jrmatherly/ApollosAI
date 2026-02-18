import { useTranslation } from "react-i18next";

export default function AdminModelsPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$MODELS_TITLE", "Models")}
      </h3>
      <p className="text-tertiary">
        {t(
          "ADMIN$MODELS_DESCRIPTION",
          "Configure allowed LLM models for your organization.",
        )}
      </p>
    </div>
  );
}
