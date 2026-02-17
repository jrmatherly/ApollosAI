import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "test-utils";
import { OrgSelector } from "#/components/features/workspace/org-selector";

// Mock the hooks
const mockOrgs = [
  { id: "org-1", name: "Org One", slug: "org-one" },
  { id: "org-2", name: "Org Two", slug: "org-two" },
];

const mockSwitchOrg = vi.fn();

vi.mock("#/hooks/query/use-organizations", () => ({
  useOrganizations: () => ({
    data: mockOrgs,
    isLoading: false,
  }),
}));

vi.mock("#/hooks/mutation/use-switch-org", () => ({
  useSwitchOrg: () => ({
    mutate: mockSwitchOrg,
  }),
}));

vi.mock("#/hooks/query/use-is-authed", () => ({
  useIsAuthed: () => ({
    data: true,
    isLoading: false,
  }),
}));

describe("OrgSelector", () => {
  it("renders dropdown with org list", () => {
    renderWithProviders(
      <OrgSelector currentOrgId="org-1" />,
    );

    const select = screen.getByRole("combobox", { name: /select organization/i });
    expect(select).toBeInTheDocument();

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Org One");
    expect(options[1]).toHaveTextContent("Org Two");
  });

  it("calls switchOrg on selection change", async () => {
    const user = userEvent.setup();
    const onOrgChange = vi.fn();

    renderWithProviders(
      <OrgSelector currentOrgId="org-1" onOrgChange={onOrgChange} />,
    );

    const select = screen.getByRole("combobox", { name: /select organization/i });
    await user.selectOptions(select, "org-2");

    expect(mockSwitchOrg).toHaveBeenCalledWith("org-2");
    expect(onOrgChange).toHaveBeenCalledWith("org-2");
  });
});
