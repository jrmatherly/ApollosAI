import { useOrganizations } from "#/hooks/query/use-organizations";
import { useSwitchOrg } from "#/hooks/mutation/use-switch-org";

interface OrgSelectorProps {
  currentOrgId: string | null;
  onOrgChange?: (orgId: string) => void;
}

export function OrgSelector({ currentOrgId, onOrgChange }: OrgSelectorProps) {
  const { data: organizations, isLoading } = useOrganizations();
  const { mutate: switchOrg } = useSwitchOrg();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const orgId = e.target.value;
    switchOrg(orgId);
    onOrgChange?.(orgId);
  };

  if (isLoading || !organizations?.length) {
    return null;
  }

  return (
    <select
      aria-label="Select organization"
      value={currentOrgId ?? ""}
      onChange={handleChange}
      className="w-full text-sm bg-base border border-neutral-600 rounded px-2 py-1 text-white truncate"
    >
      {organizations.map((org) => (
        <option key={org.id} value={org.id}>
          {org.name}
        </option>
      ))}
    </select>
  );
}
