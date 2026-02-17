import { useQuery } from "@tanstack/react-query";

import AdminService from "#/api/admin-service/admin-service.api";
import type { AuditLogParams } from "#/api/admin-service/admin.types";

export const useAuditLog = (orgId: string | null, params?: AuditLogParams) =>
  useQuery({
    queryKey: ["audit-log", orgId, params],
    queryFn: () => AdminService.getAuditLogs(orgId!, params),
    enabled: !!orgId,
    staleTime: 1000 * 30, // 30 seconds — audit logs change frequently
  });
