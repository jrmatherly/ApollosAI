import React from "react";
import { useTranslation } from "react-i18next";

import { useOrgMembers } from "#/hooks/query/use-org-members";
import { useInviteMember } from "#/hooks/mutation/use-invite-member";
import { useRemoveMember } from "#/hooks/mutation/use-remove-member";
import { useUpdateRole } from "#/hooks/mutation/use-update-role";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { BrandButton } from "#/components/features/settings/brand-button";
import { MemberList } from "#/components/features/admin/member-list";
import { InviteMemberModal } from "#/components/features/admin/invite-member-modal";

export default function AdminMembersPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: members, isLoading } = useOrgMembers(orgId);
  const inviteMember = useInviteMember(orgId ?? "");
  const removeMember = useRemoveMember(orgId ?? "");
  const updateRole = useUpdateRole(orgId ?? "");

  const [showInviteModal, setShowInviteModal] = React.useState(false);

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
        <BrandButton
          type="button"
          variant="primary"
          onClick={() => setShowInviteModal(true)}
        >
          {t("ADMIN$INVITE_MEMBER", "Invite Member")}
        </BrandButton>
      </div>
      {members && members.length > 0 ? (
        <MemberList
          members={members}
          onRoleChange={(userId, role) =>
            updateRole.mutate({
              userId,
              body: {
                role: role as "owner" | "admin" | "manager" | "member",
              },
            })
          }
          onRemove={(userId) => removeMember.mutate(userId)}
          isUpdating={updateRole.isPending || removeMember.isPending}
        />
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_MEMBERS", "No members found.")}
        </p>
      )}
      {showInviteModal && (
        <InviteMemberModal
          onSubmit={(body) => {
            inviteMember.mutate(body, {
              onSuccess: () => setShowInviteModal(false),
            });
          }}
          onClose={() => setShowInviteModal(false)}
          isPending={inviteMember.isPending}
        />
      )}
    </div>
  );
}
