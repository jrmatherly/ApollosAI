import { openHands } from "../open-hands-axios";

export interface MCPServer {
  id: string;
  name: string;
  server_type: "stdio" | "sse" | "shttp";
  enabled: boolean;
  approved: boolean;
  description: string | null;
  created_at: string;
}

export interface CreateMCPServerBody {
  name: string;
  server_type: "stdio" | "sse" | "shttp";
  config_json: Record<string, unknown>;
  description?: string;
}

export interface UpdateMCPServerBody {
  name?: string;
  config_json?: Record<string, unknown>;
  enabled?: boolean;
  description?: string;
}

class MCPAdminService {
  static async getMCPServers(orgId: string): Promise<MCPServer[]> {
    const { data } = await openHands.get<MCPServer[]>(
      `/api/orgs/${orgId}/mcp/servers`,
    );
    return data;
  }

  static async addMCPServer(
    orgId: string,
    body: CreateMCPServerBody,
  ): Promise<MCPServer> {
    const { data } = await openHands.post<MCPServer>(
      `/api/orgs/${orgId}/mcp/servers`,
      body,
    );
    return data;
  }

  static async updateMCPServer(
    orgId: string,
    serverId: string,
    body: UpdateMCPServerBody,
  ): Promise<MCPServer> {
    const { data } = await openHands.put<MCPServer>(
      `/api/orgs/${orgId}/mcp/servers/${serverId}`,
      body,
    );
    return data;
  }

  static async removeMCPServer(orgId: string, serverId: string): Promise<void> {
    await openHands.delete(`/api/orgs/${orgId}/mcp/servers/${serverId}`);
  }
}

export default MCPAdminService;
