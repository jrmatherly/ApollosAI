import { useTranslation } from "react-i18next";

import { useTeams } from "#/hooks/query/use-teams";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export default function AdminTeamsPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: teams, isLoading } = useTeams(orgId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$TEAMS_TITLE", "Teams")}
      </h3>
      {teams && teams.length > 0 ? (
        <div className="rounded-lg border border-tertiary">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tertiary text-left text-tertiary">
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$TEAM_NAME", "Name")}
                </th>
              </tr>
            </thead>
            <tbody>
              {teams.map((team) => (
                <tr
                  key={team.id}
                  className="border-b border-tertiary last:border-b-0"
                >
                  <td className="px-4 py-3">{team.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_TEAMS", "No teams found.")}
        </p>
      )}
    </div>
  );
}
