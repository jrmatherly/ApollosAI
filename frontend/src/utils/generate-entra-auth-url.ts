/**
 * Generates the URL for Entra ID (Microsoft) OAuth login via the backend.
 * The backend handles the MSAL flow at /api/auth/login.
 *
 * @param returnTo - Path to redirect to after successful login (defaults to "/")
 * @returns The backend auth login URL with encoded returnTo parameter
 */
export const generateEntraAuthUrl = (returnTo: string = "/"): string =>
  `/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
