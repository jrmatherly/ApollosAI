import { ws } from "msw";
import { server } from "#/mocks/node";

/**
 * Creates a WebSocket link for MSW testing.
 *
 * IMPORTANT: Do NOT create separate setupServer() instances for WebSocket tests.
 * The global MSW server from vitest.setup.ts is already running. Use server.use()
 * to add WebSocket handlers at runtime. See __tests__/MSW.md.
 *
 * @param url - WebSocket URL to mock (default: "ws://localhost/events/socket")
 * @returns MSW WebSocket link
 */
export const createWebSocketLink = (url = "ws://localhost/events/socket") =>
  ws.link(url);

/**
 * Adds a WebSocket connection handler to the global MSW server.
 * The handler is removed automatically by server.resetHandlers() in afterEach.
 *
 * @param wsLink - WebSocket link to register a connection handler for
 */
export const addWebSocketHandler = (wsLink: ReturnType<typeof ws.link>) => {
  server.use(
    wsLink.addEventListener("connection", ({ server: wsServer }) => {
      wsServer.connect();
    }),
  );
};

/**
 * Creates a complete WebSocket testing setup with link and registers the handler.
 * Uses the global MSW server — no separate setupServer() instance.
 *
 * @param url - WebSocket URL to mock (default: "ws://localhost/events/socket")
 * @returns Object containing the WebSocket link and the global server reference
 */
export const createWebSocketTestSetup = (
  url = "ws://localhost/events/socket",
) => {
  const wsLink = createWebSocketLink(url);
  return { wsLink, server };
};

/**
 * Standard WebSocket test setup for conversation WebSocket handler tests.
 * Updated to use the V1 WebSocket URL pattern: /sockets/events/{conversationId}
 * Uses a wildcard pattern to match any conversation ID.
 */
export const conversationWebSocketTestSetup = () =>
  createWebSocketTestSetup("ws://localhost:3000/sockets/events/*");
