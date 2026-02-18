import { openHands } from "../open-hands-axios";

import type {
  AuditLogParams,
  InviteMemberBody,
  OrgMember,
  PaginatedAuditLogResponse,
  UpdateRoleBody,
} from "./admin.types";

class AdminService {
  static async getOrgMembers(orgId: string): Promise<OrgMember[]> {
    const { data } = await openHands.get<OrgMember[]>(
      `/api/orgs/${orgId}/members`,
    );
    return data;
  }

  static async inviteMember(
    orgId: string,
    body: InviteMemberBody,
  ): Promise<OrgMember> {
    const { data } = await openHands.post<OrgMember>(
      `/api/orgs/${orgId}/members`,
      body,
    );
    return data;
  }

  static async removeMember(orgId: string, userId: string): Promise<void> {
    await openHands.delete(`/api/orgs/${orgId}/members/${userId}`);
  }

  static async updateRole(
    orgId: string,
    userId: string,
    body: UpdateRoleBody,
  ): Promise<OrgMember> {
    const { data } = await openHands.patch<OrgMember>(
      `/api/orgs/${orgId}/members/${userId}/role`,
      body,
    );
    return data;
  }

  static async getAuditLogs(
    orgId: string,
    params?: AuditLogParams,
  ): Promise<PaginatedAuditLogResponse> {
    const { data } = await openHands.get<PaginatedAuditLogResponse>(
      `/api/admin/orgs/${orgId}/audit`,
      { params },
    );
    return data;
  }
}

export default AdminService;
