import React from "react";
import { useTranslation } from "react-i18next";

import { BrandButton } from "#/components/features/settings/brand-button";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";
import type { InviteMemberBody } from "#/api/admin-service/admin.types";

import { RoleSelector } from "./role-selector";

interface InviteMemberModalProps {
  onSubmit: (body: InviteMemberBody) => void;
  onClose: () => void;
  isPending: boolean;
}

export function InviteMemberModal({
  onSubmit,
  onClose,
  isPending,
}: InviteMemberModalProps) {
  const { t } = useTranslation();
  const [userId, setUserId] = React.useState("");
  const [role, setRole] = React.useState<InviteMemberBody["role"]>("member");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) return;
    onSubmit({ user_id: userId.trim(), role });
  };

  return (
    <ModalBackdrop onClose={onClose}>
      <form
        onSubmit={handleSubmit}
        className="bg-base-secondary p-6 rounded-xl flex flex-col gap-4 border border-tertiary min-w-[360px]"
      >
        <h3 className="text-lg font-semibold">
          {t("ADMIN$INVITE_MEMBER", "Invite Member")}
        </h3>
        <div className="flex flex-col gap-2">
          <label htmlFor="user-id" className="text-sm text-tertiary">
            {t("ADMIN$USER_ID", "User ID")}
          </label>
          <input
            id="user-id"
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder={t("ADMIN$USER_ID_PLACEHOLDER", "Enter user ID...")}
            className="rounded border border-tertiary bg-base px-3 py-2 text-sm"
            required
          />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="role-select" className="text-sm text-tertiary">
            {t("ADMIN$MEMBER_ROLE", "Role")}
          </label>
          <RoleSelector value={role} onChange={setRole} />
        </div>
        <div className="flex gap-2 justify-end">
          <BrandButton
            type="button"
            variant="secondary"
            onClick={onClose}
            isDisabled={isPending}
          >
            {t("BUTTON$CANCEL", "Cancel")}
          </BrandButton>
          <BrandButton
            type="submit"
            variant="primary"
            isDisabled={isPending || !userId.trim()}
          >
            {isPending
              ? t("ADMIN$INVITING", "Inviting...")
              : t("ADMIN$INVITE", "Invite")}
          </BrandButton>
        </div>
      </form>
    </ModalBackdrop>
  );
}
