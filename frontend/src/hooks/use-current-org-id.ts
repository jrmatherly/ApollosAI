import { useOrganizations } from "#/hooks/query/use-organizations";

export const useCurrentOrgId = (): string | null => {
  const { data: orgs } = useOrganizations();
  return orgs?.[0]?.id ?? null;
};
