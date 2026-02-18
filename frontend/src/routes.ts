import {
  type RouteConfig,
  layout,
  index,
  route,
} from "@react-router/dev/routes";

export default [
  route("login", "routes/login.tsx"),
  layout("routes/root-layout.tsx", [
    index("routes/home.tsx"),
    route("accept-tos", "routes/accept-tos.tsx"),
    route("settings", "routes/settings.tsx", [
      index("routes/llm-settings.tsx"),
      route("mcp", "routes/mcp-settings.tsx"),
      route("user", "routes/user-settings.tsx"),
      route("integrations", "routes/git-settings.tsx"),
      route("app", "routes/app-settings.tsx"),
      route("billing", "routes/billing.tsx"),
      route("secrets", "routes/secrets-settings.tsx"),
      route("api-keys", "routes/api-keys.tsx"),
    ]),
    route("admin", "routes/admin-layout.tsx", [
      index("routes/admin-members.tsx"),
      route("teams", "routes/admin-teams.tsx"),
      route("integrations", "routes/admin-integrations.tsx"),
      route("mcp", "routes/admin-mcp.tsx"),
      route("models", "routes/admin-models.tsx"),
      route("api-keys", "routes/admin-api-keys.tsx"),
      route("audit", "routes/admin-audit.tsx"),
      route("alerts", "routes/admin-alerts.tsx"),
    ]),
    route("conversations/:conversationId", "routes/conversation.tsx"),
    route("microagent-management", "routes/microagent-management.tsx"),
    route("oauth/device/verify", "routes/device-verify.tsx"),
  ]),
  // Shared routes that don't require authentication
  route(
    "shared/conversations/:conversationId",
    "routes/shared-conversation.tsx",
  ),
] satisfies RouteConfig;
