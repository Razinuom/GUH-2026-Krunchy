import { useNavigate } from "react-router-dom";
import { Disclaimer, Page } from "@/components/layout/Page";
import { PageHeader } from "@/components/layout/PageHeader";
import { PersonCard } from "@/components/family/PersonCard";
import { SourceNote } from "@/components/DataState";
import { useForecasts } from "@/lib/hooks";
import { useHeirloom } from "@/state/HeirloomContext";

export default function Family() {
  const { familyData, setMemberId } = useHeirloom();
  const forecasts = useForecasts(familyData.members.map((m) => m.id));
  const navigate = useNavigate();
  const okafor = familyData.id === "okafor";

  return (
    <Page>
      <PageHeader
        page="family"
        label="The Family"
        title={`The ${familyData.name}`}
        lead={
          okafor
            ? "No inheritance to plan around, and the plan still works: small regular saving, the Lifetime ISA bonus and steering clear of debt traps."
            : "Three generations, one plan. Pick a person to see their next 90 days."
        }
      />
      <div className="grid grid-cols-3 divide-x divide-line md720:grid-cols-1 md720:divide-x-0 md720:divide-y">
        {familyData.members.map((m) => (
          <PersonCard
            key={m.id}
            member={m}
            forecast={forecasts[m.id]}
            onSelect={() => {
              setMemberId(m.id);
              navigate("/forecast");
            }}
          />
        ))}
      </div>
      <hr className="mb-5 mt-10 border-line" />
      <Disclaimer />
      {(() => {
        const first = Object.values(forecasts).find(Boolean);
        return (
          <SourceNote
            className="mt-1"
            source={first?.source ?? "live"}
            live="Balances come from synthetic transactions calibrated to the ONS Living Costs and Food Survey, ready for the NatWest Account and Transaction API."
          />
        );
      })()}
    </Page>
  );
}
