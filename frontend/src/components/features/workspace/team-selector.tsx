import { useTeams } from "#/hooks/query/use-teams";
import { useSwitchTeam } from "#/hooks/mutation/use-switch-team";

interface TeamSelectorProps {
  currentOrgId: string | null;
  currentTeamId: string | null;
  onTeamChange?: (teamId: string) => void;
}

export function TeamSelector({
  currentOrgId,
  currentTeamId,
  onTeamChange,
}: TeamSelectorProps) {
  const { data: teams, isLoading } = useTeams(currentOrgId);
  const { mutate: switchTeam } = useSwitchTeam();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const teamId = e.target.value;
    switchTeam(teamId);
    onTeamChange?.(teamId);
  };

  if (isLoading || !teams?.length) {
    return null;
  }

  return (
    <select
      aria-label="Select team"
      value={currentTeamId ?? ""}
      onChange={handleChange}
      className="w-full text-sm bg-base border border-neutral-600 rounded px-2 py-1 text-white truncate"
    >
      {teams.map((team) => (
        <option key={team.id} value={team.id}>
          {team.name}
        </option>
      ))}
    </select>
  );
}
