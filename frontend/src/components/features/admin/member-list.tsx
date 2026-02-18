import React from "react";
import { useTranslation } from "react-i18next";

import type { OrgMember } from "#/api/admin-service/admin.types";
import { ConfirmationModal } from "#/components/shared/modals/confirmation-modal";

import { RoleSelector } from "./role-selector";

interface MemberListProps {
  members: OrgMember[];
  onRoleChange: (userId: string, role: string) => void;
  onRemove: (userId: string) => void;
  isUpdating: boolean;
}

export function MemberList({
  members,
  onRoleChange,
  onRemove,
  isUpdating,
}: MemberListProps) {
  const { t } = useTranslation();
  const [removingUserId, setRemovingUserId] = React.useState<string | null>(
    null,
  );

  return (
    <>
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
              <th className="px-4 py-3 font-medium w-24" />
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr
                key={member.user_id}
                className="border-b border-tertiary last:border-b-0"
              >
                <td className="px-4 py-3">{member.email ?? member.user_id}</td>
                <td className="px-4 py-3">
                  <RoleSelector
                    value={member.role_name}
                    onChange={(role) => onRoleChange(member.user_id, role)}
                    disabled={isUpdating}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => setRemovingUserId(member.user_id)}
                    disabled={isUpdating}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
                  >
                    {t("ADMIN$REMOVE", "Remove")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {removingUserId && (
        <ConfirmationModal
          text={t(
            "ADMIN$CONFIRM_REMOVE_MEMBER",
            "Are you sure you want to remove this member?",
          )}
          onConfirm={() => {
            onRemove(removingUserId);
            setRemovingUserId(null);
          }}
          onCancel={() => setRemovingUserId(null)}
        />
      )}
    </>
  );
}
