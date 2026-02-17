import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "test-utils";
import { TeamSelector } from "#/components/features/workspace/team-selector";

// Mock the hooks
const mockTeams = [
  { id: "team-1", name: "Team Alpha", slug: "team-alpha", org_id: "org-1" },
  { id: "team-2", name: "Team Beta", slug: "team-beta", org_id: "org-1" },
];

const mockSwitchTeam = vi.fn();

vi.mock("#/hooks/query/use-teams", () => ({
  useTeams: () => ({
    data: mockTeams,
    isLoading: false,
  }),
}));

vi.mock("#/hooks/mutation/use-switch-team", () => ({
  useSwitchTeam: () => ({
    mutate: mockSwitchTeam,
  }),
}));

vi.mock("#/hooks/query/use-is-authed", () => ({
  useIsAuthed: () => ({
    data: true,
    isLoading: false,
  }),
}));

describe("TeamSelector", () => {
  it("renders dropdown with team list", () => {
    renderWithProviders(
      <TeamSelector currentOrgId="org-1" currentTeamId="team-1" />,
    );

    const select = screen.getByRole("combobox", { name: /select team/i });
    expect(select).toBeInTheDocument();

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Team Alpha");
    expect(options[1]).toHaveTextContent("Team Beta");
  });

  it("calls switchTeam on selection change", async () => {
    const user = userEvent.setup();
    const onTeamChange = vi.fn();

    renderWithProviders(
      <TeamSelector
        currentOrgId="org-1"
        currentTeamId="team-1"
        onTeamChange={onTeamChange}
      />,
    );

    const select = screen.getByRole("combobox", { name: /select team/i });
    await user.selectOptions(select, "team-2");

    expect(mockSwitchTeam).toHaveBeenCalledWith("team-2");
    expect(onTeamChange).toHaveBeenCalledWith("team-2");
  });
});
