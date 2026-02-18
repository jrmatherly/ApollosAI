export interface OrgMember {
  user_id: string;
  email: string | null;
  role_name: string;
  role_rank: number;
}

export interface InviteMemberBody {
  user_id: string;
  role: "owner" | "admin" | "manager" | "member";
}

export interface UpdateRoleBody {
  role: "owner" | "admin" | "manager" | "member";
}

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface PaginatedAuditLogResponse {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogParams {
  limit?: number;
  offset?: number;
  action?: string;
  actor_id?: string;
}
