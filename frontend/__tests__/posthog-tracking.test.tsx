import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  vi,
} from "vitest";
import { screen, waitFor, render, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ws } from "msw";
import { createMockAgentErrorEvent } from "#/mocks/mock-ws-helpers";
import { ConversationWebSocketProvider } from "#/contexts/conversation-websocket-context";
import { server } from "#/mocks/node";
import { ConnectionStatusComponent } from "./helpers/websocket-test-components";

// Mock the tracking function
const mockTrackCreditLimitReached = vi.fn();

// Mock useTracking hook
vi.mock("#/hooks/use-tracking", () => ({
  useTracking: () => ({
    trackCreditLimitReached: mockTrackCreditLimitReached,
    trackLoginButtonClick: vi.fn(),
    trackConversationCreated: vi.fn(),
    trackPushButtonClick: vi.fn(),
    trackPullButtonClick: vi.fn(),
    trackCreatePrButtonClick: vi.fn(),
    trackGitProviderConnected: vi.fn(),
    trackUserSignupCompleted: vi.fn(),
    trackCreditsPurchased: vi.fn(),
  }),
}));

// Mock useActiveConversation hook
vi.mock("#/hooks/query/use-active-conversation", () => ({
  useActiveConversation: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
}));

// MSW WebSocket link — uses the global MSW server (no separate setupServer)
const wsLink = ws.link("ws://localhost:3000/sockets/events/*");

beforeEach(() => {
  // Register the WebSocket connection handler on the global server.
  // server.resetHandlers() in vitest.setup.ts afterEach removes these automatically.
  server.use(
    wsLink.addEventListener("connection", ({ server: wsServer }) => {
      wsServer.connect();
    }),
  );
});

afterEach(() => {
  // Force-close all WebSocket connections to prevent stale clients leaking between tests
  wsLink.clients.forEach((client) => client.close());
  mockTrackCreditLimitReached.mockClear();
  cleanup();
});

// Helper function to render components with all necessary providers
function renderWithProviders(
  children: React.ReactNode,
  conversationId = "test-conversation-123",
  conversationUrl = "http://localhost:3000/api/conversations/test-conversation-123",
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ConversationWebSocketProvider
        conversationId={conversationId}
        conversationUrl={conversationUrl}
        sessionApiKey={null}
      >
        {children}
      </ConversationWebSocketProvider>
    </QueryClientProvider>,
  );
}

describe("PostHog Analytics Tracking", () => {
  describe("Credit Limit Tracking", () => {
    it("should track credit_limit_reached when AgentErrorEvent contains budget error", async () => {
      // Create a mock AgentErrorEvent with budget-related error message
      const mockBudgetErrorEvent = createMockAgentErrorEvent({
        error: "ExceededBudget: Task exceeded maximum budget of $10.00",
      });

      // Set up MSW to send the budget error event when connection is established
      server.use(
        wsLink.addEventListener("connection", ({ client, server: wsServer }) => {
          wsServer.connect();
          // Send the mock budget error event after connection
          client.send(JSON.stringify(mockBudgetErrorEvent));
        }),
      );

      // Render with all providers
      renderWithProviders(<ConnectionStatusComponent />);

      // Wait for connection to be established
      await waitFor(() => {
        expect(screen.getByTestId("connection-state")).toHaveTextContent(
          "OPEN",
        );
      });

      // Wait for the tracking event to be captured
      await waitFor(() => {
        expect(mockTrackCreditLimitReached).toHaveBeenCalledWith(
          expect.objectContaining({
            conversationId: "test-conversation-123",
          }),
        );
      });
    });

    it("should track credit_limit_reached when AgentErrorEvent contains 'credit' keyword", async () => {
      // Create error with "credit" keyword (case-insensitive)
      const mockCreditErrorEvent = createMockAgentErrorEvent({
        error: "Insufficient CREDIT to complete this operation",
      });

      server.use(
        wsLink.addEventListener("connection", ({ client, server: wsServer }) => {
          wsServer.connect();
          client.send(JSON.stringify(mockCreditErrorEvent));
        }),
      );

      renderWithProviders(<ConnectionStatusComponent />);

      await waitFor(() => {
        expect(screen.getByTestId("connection-state")).toHaveTextContent(
          "OPEN",
        );
      });

      await waitFor(() => {
        expect(mockTrackCreditLimitReached).toHaveBeenCalledWith(
          expect.objectContaining({
            conversationId: "test-conversation-123",
          }),
        );
      });
    });

    it("should NOT track credit_limit_reached for non-budget errors", async () => {
      // Create a regular error without budget/credit keywords
      const mockRegularErrorEvent = createMockAgentErrorEvent({
        error: "Failed to execute command: Permission denied",
      });

      server.use(
        wsLink.addEventListener("connection", ({ client, server: wsServer }) => {
          wsServer.connect();
          client.send(JSON.stringify(mockRegularErrorEvent));
        }),
      );

      renderWithProviders(<ConnectionStatusComponent />);

      // Wait for connection and error to be processed
      await waitFor(() => {
        expect(screen.getByTestId("connection-state")).toHaveTextContent(
          "OPEN",
        );
      });

      // Verify that credit_limit_reached was NOT tracked
      expect(mockTrackCreditLimitReached).not.toHaveBeenCalled();
    });

    it("should only track credit_limit_reached once per error event", async () => {
      const mockBudgetErrorEvent = createMockAgentErrorEvent({
        error: "Budget exceeded: $10.00 limit reached",
      });

      server.use(
        wsLink.addEventListener("connection", ({ client, server: wsServer }) => {
          wsServer.connect();
          // Send the same error event twice
          client.send(JSON.stringify(mockBudgetErrorEvent));
          client.send(
            JSON.stringify({ ...mockBudgetErrorEvent, id: "different-id" }),
          );
        }),
      );

      renderWithProviders(<ConnectionStatusComponent />);

      await waitFor(() => {
        expect(screen.getByTestId("connection-state")).toHaveTextContent(
          "OPEN",
        );
      });

      await waitFor(() => {
        expect(mockTrackCreditLimitReached).toHaveBeenCalledTimes(2);
      });

      // Both calls should be for credit_limit_reached (once per event)
      expect(mockTrackCreditLimitReached).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({
          conversationId: "test-conversation-123",
        }),
      );
      expect(mockTrackCreditLimitReached).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({
          conversationId: "test-conversation-123",
        }),
      );
    });
  });
});
