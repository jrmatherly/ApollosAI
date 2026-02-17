import { openHands } from "../open-hands-axios";

export interface Integration {
  type: string;
  enabled: boolean;
  registered: boolean;
}

export interface IntegrationConfig {
  integration_type: string;
  enabled: boolean;
  config: Record<string, unknown>;
}

export interface SaveIntegrationConfigBody {
  enabled: boolean;
  config: Record<string, unknown>;
}

class AdminIntegrationService {
  static async getIntegrations(orgId: string): Promise<Integration[]> {
    const { data } = await openHands.get<Integration[]>(
      `/api/orgs/${orgId}/integrations`,
    );
    return data;
  }

  static async getIntegrationConfig(
    orgId: string,
    integrationType: string,
  ): Promise<IntegrationConfig> {
    const { data } = await openHands.get<IntegrationConfig>(
      `/api/orgs/${orgId}/integrations/${integrationType}`,
    );
    return data;
  }

  static async saveIntegrationConfig(
    orgId: string,
    integrationType: string,
    body: SaveIntegrationConfigBody,
  ): Promise<IntegrationConfig> {
    const { data } = await openHands.put<IntegrationConfig>(
      `/api/orgs/${orgId}/integrations/${integrationType}`,
      body,
    );
    return data;
  }

  static async testIntegration(
    orgId: string,
    integrationType: string,
  ): Promise<{ status: string }> {
    const { data } = await openHands.post<{ status: string }>(
      `/api/orgs/${orgId}/integrations/${integrationType}/test`,
    );
    return data;
  }
}

export default AdminIntegrationService;
