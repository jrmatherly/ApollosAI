import { useTranslation } from "react-i18next";

const ROLES = ["owner", "admin", "manager", "member"] as const;
type Role = (typeof ROLES)[number];

interface RoleSelectorProps {
  value: string;
  onChange: (role: Role) => void;
  disabled?: boolean;
}

export function RoleSelector({ value, onChange, disabled }: RoleSelectorProps) {
  const { t } = useTranslation();

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as Role)}
      disabled={disabled}
      className="rounded border border-tertiary bg-base px-2 py-1 text-sm capitalize disabled:opacity-50"
    >
      {ROLES.map((role) => (
        <option key={role} value={role}>
          {t(`ADMIN$ROLE_${role.toUpperCase()}`, role)}
        </option>
      ))}
    </select>
  );
}
