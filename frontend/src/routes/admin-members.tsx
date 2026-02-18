import { useTranslation } from "react-i18next";

import { useOrgMembers } from "#/hooks/query/use-org-members";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export default function AdminMembersPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: members, isLoading } = useOrgMembers(orgId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {t("ADMIN$MEMBERS_TITLE", "Members")}
        </h3>
      </div>
      {members && members.length > 0 ? (
        <div className="rounded-lg border border-tertiary">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tertiary text-left text-tertiary">
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$MEMBER_EMAIL", "Email")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$MEMBER_ROLE", "Role")}
                </th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr
                  key={member.user_id}
                  className="border-b border-tertiary last:border-b-0"
                >
                  <td className="px-4 py-3">
                    {member.email ?? member.user_id}
                  </td>
                  <td className="px-4 py-3 capitalize">{member.role_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_MEMBERS", "No members found.")}
        </p>
      )}
    </div>
  );
}
