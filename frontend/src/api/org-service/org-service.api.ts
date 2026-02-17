import { openHands } from "../open-hands-axios";

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface Team {
  id: string;
  name: string;
  slug: string;
  org_id: string;
}

class OrgService {
  static async getOrganizations(): Promise<Organization[]> {
    const { data } = await openHands.get<Organization[]>("/api/orgs");
    return data;
  }

  static async getTeams(orgId: string): Promise<Team[]> {
    const { data } = await openHands.get<Team[]>(`/api/orgs/${orgId}/teams`);
    return data;
  }

  static async switchOrg(orgId: string): Promise<void> {
    await openHands.post("/api/orgs/switch", { org_id: orgId });
  }

  static async switchTeam(teamId: string): Promise<void> {
    await openHands.post("/api/teams/switch", { team_id: teamId });
  }
}

export default OrgService;
