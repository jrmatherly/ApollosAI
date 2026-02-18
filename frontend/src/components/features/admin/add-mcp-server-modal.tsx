import React from "react";
import { useTranslation } from "react-i18next";

import type { CreateMCPServerBody } from "#/api/mcp-admin-service/mcp-admin-service.api";
import { BrandButton } from "#/components/features/settings/brand-button";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";

const SERVER_TYPES = ["stdio", "sse", "shttp"] as const;

interface AddMCPServerModalProps {
  onSubmit: (body: CreateMCPServerBody) => void;
  onClose: () => void;
  isPending: boolean;
}

export function AddMCPServerModal({
  onSubmit,
  onClose,
  isPending,
}: AddMCPServerModalProps) {
  const { t } = useTranslation();
  const [name, setName] = React.useState("");
  const [serverType, setServerType] =
    React.useState<CreateMCPServerBody["server_type"]>("stdio");
  const [description, setDescription] = React.useState("");

  // stdio fields
  const [command, setCommand] = React.useState("");
  const [args, setArgs] = React.useState("");
  const [envVars, setEnvVars] = React.useState("");

  // sse/shttp fields
  const [url, setUrl] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    let configJson: Record<string, unknown>;
    if (serverType === "stdio") {
      configJson = {
        command: command.trim(),
        args: args
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
        env: envVars
          .split("\n")
          .filter(Boolean)
          .reduce<Record<string, string>>((acc, line) => {
            const eqIdx = line.indexOf("=");
            if (eqIdx > 0) {
              acc[line.slice(0, eqIdx).trim()] = line.slice(eqIdx + 1).trim();
            }
            return acc;
          }, {}),
      };
    } else {
      configJson = {
        url: url.trim(),
        ...(apiKey.trim() && { api_key: apiKey.trim() }),
      };
    }

    onSubmit({
      name: name.trim(),
      server_type: serverType,
      config_json: configJson,
      ...(description.trim() && { description: description.trim() }),
    });
  };

  return (
    <ModalBackdrop onClose={onClose}>
      <form
        onSubmit={handleSubmit}
        className="bg-base-secondary p-6 rounded-xl flex flex-col gap-4 border border-tertiary min-w-[420px] max-w-lg"
      >
        <h3 className="text-lg font-semibold">
          {t("ADMIN$ADD_MCP_SERVER", "Add MCP Server")}
        </h3>

        <div className="flex flex-col gap-2">
          <label htmlFor="mcp-name" className="text-sm text-tertiary">
            {t("ADMIN$MCP_NAME", "Name")}
          </label>
          <input
            id="mcp-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("ADMIN$MCP_NAME_PLACEHOLDER", "Server name...")}
            className="rounded border border-tertiary bg-base px-3 py-2 text-sm"
            required
          />
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="mcp-type" className="text-sm text-tertiary">
            {t("ADMIN$MCP_TYPE", "Type")}
          </label>
          <select
            id="mcp-type"
            value={serverType}
            onChange={(e) =>
              setServerType(
                e.target.value as CreateMCPServerBody["server_type"],
              )
            }
            className="rounded border border-tertiary bg-base px-2 py-2 text-sm"
          >
            {SERVER_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="mcp-description" className="text-sm text-tertiary">
            {t("ADMIN$MCP_DESCRIPTION", "Description (optional)")}
          </label>
          <input
            id="mcp-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="rounded border border-tertiary bg-base px-3 py-2 text-sm"
          />
        </div>

        {serverType === "stdio" ? (
          <>
            <div className="flex flex-col gap-2">
              <label htmlFor="mcp-command" className="text-sm text-tertiary">
                {t("ADMIN$MCP_COMMAND", "Command")}
              </label>
              <input
                id="mcp-command"
                type="text"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="npx -y @modelcontextprotocol/server-..."
                className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="mcp-args" className="text-sm text-tertiary">
                {t("ADMIN$MCP_ARGS", "Arguments (comma-separated)")}
              </label>
              <input
                id="mcp-args"
                type="text"
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="mcp-env" className="text-sm text-tertiary">
                {t(
                  "ADMIN$MCP_ENV_VARS",
                  "Environment Variables (KEY=value, one per line)",
                )}
              </label>
              <textarea
                id="mcp-env"
                value={envVars}
                onChange={(e) => setEnvVars(e.target.value)}
                rows={3}
                placeholder={"API_KEY=sk-...\nDEBUG=true"}
                className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
              />
            </div>
          </>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              <label htmlFor="mcp-url" className="text-sm text-tertiary">
                {t("ADMIN$MCP_URL", "Server URL")}
              </label>
              <input
                id="mcp-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://..."
                className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="mcp-api-key" className="text-sm text-tertiary">
                {t("ADMIN$MCP_API_KEY", "API Key (optional)")}
              </label>
              <input
                id="mcp-api-key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
              />
            </div>
          </>
        )}

        <div className="flex gap-2 justify-end">
          <BrandButton
            type="button"
            variant="secondary"
            onClick={onClose}
            isDisabled={isPending}
          >
            {t("BUTTON$CANCEL", "Cancel")}
          </BrandButton>
          <BrandButton
            type="submit"
            variant="primary"
            isDisabled={isPending || !name.trim()}
          >
            {isPending ? t("ADMIN$ADDING", "Adding...") : t("ADMIN$ADD", "Add")}
          </BrandButton>
        </div>
      </form>
    </ModalBackdrop>
  );
}
