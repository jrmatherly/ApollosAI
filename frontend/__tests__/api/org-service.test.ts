import { describe, it, expect, vi, beforeEach } from "vitest";
import OrgService from "../../src/api/org-service/org-service.api";

// Mock the axios instance used by openHands
vi.mock("../../src/api/open-hands-axios", () => ({
  openHands: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { openHands } from "../../src/api/open-hands-axios";

describe("OrgService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getOrganizations", () => {
    it("fetches org list from /api/orgs", async () => {
      const mockOrgs = [
        { id: "1", name: "Org 1", slug: "org-1" },
        { id: "2", name: "Org 2", slug: "org-2" },
      ];
      vi.mocked(openHands.get).mockResolvedValue({ data: mockOrgs });

      const result = await OrgService.getOrganizations();

      expect(openHands.get).toHaveBeenCalledWith("/api/orgs");
      expect(result).toEqual(mockOrgs);
    });
  });

  describe("getTeams", () => {
    it("fetches teams for a given org", async () => {
      const mockTeams = [
        { id: "t1", name: "Team A", slug: "team-a", org_id: "org-1" },
      ];
      vi.mocked(openHands.get).mockResolvedValue({ data: mockTeams });

      const result = await OrgService.getTeams("org-1");

      expect(openHands.get).toHaveBeenCalledWith("/api/orgs/org-1/teams");
      expect(result).toEqual(mockTeams);
    });
  });

  describe("switchOrg", () => {
    it("posts to /api/orgs/switch with org_id", async () => {
      vi.mocked(openHands.post).mockResolvedValue({ data: {} });

      await OrgService.switchOrg("org-1");

      expect(openHands.post).toHaveBeenCalledWith("/api/orgs/switch", {
        org_id: "org-1",
      });
    });
  });

  describe("switchTeam", () => {
    it("posts to /api/teams/switch with team_id", async () => {
      vi.mocked(openHands.post).mockResolvedValue({ data: {} });

      await OrgService.switchTeam("team-1");

      expect(openHands.post).toHaveBeenCalledWith("/api/teams/switch", {
        team_id: "team-1",
      });
    });
  });
});
