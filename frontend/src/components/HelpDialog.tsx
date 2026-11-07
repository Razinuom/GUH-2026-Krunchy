import { ExternalLink } from "lucide-react";
import { useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { escalate } from "@/lib/api";
import { useHeirloom } from "@/state/HeirloomContext";

const HELP = [
  { name: "MoneyHelper", what: "Free, impartial money and pensions guidance, backed by the government.", url: "https://www.moneyhelper.org.uk/", phone: "0800 138 7777" },
  { name: "StepChange", what: "Free, confidential debt advice and debt plans.", url: "https://www.stepchange.org/", phone: "0800 138 1111" },
  { name: "Citizens Advice", what: "Help with benefits, bills, scams and consumer problems.", url: "https://www.citizensadvice.org.uk/", phone: "0800 144 8848" },
];

export function HelpDialog() {
  const { helpOpen, setHelpOpen, member } = useHeirloom();

  useEffect(() => {
    if (helpOpen) escalate(member.id, "talk_to_a_person");
  }, [helpOpen, member.id]);

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Talk to a Person</DialogTitle>
          <DialogDescription>These services are free and do not sell anything.</DialogDescription>
        </DialogHeader>
        <ul className="divide-y divide-line border-y border-line">
          {HELP.map((h) => (
            <li key={h.name} className="py-3.5">
              <a href={h.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-semibold">
                {h.name} <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <p className="text-[.9rem] text-muted">{h.what}</p>
              <p className="num mt-0.5 text-[.9rem]">Call {h.phone}</p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[.82rem] text-muted">
          In the full build, the voice agent can transfer the call to one of these services, but only with your permission.
        </p>
      </DialogContent>
    </Dialog>
  );
}
