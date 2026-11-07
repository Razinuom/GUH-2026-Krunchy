import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { escalate, snapshot } from "@/lib/api";
import type { HelpResource } from "@/lib/types";
import { useHeirloom } from "@/state/HeirloomContext";

/** "Talk to a Person": logs the handoff (POST /escalate) and lists the free services the backend returns. */
export function HelpDialog() {
  const { helpOpen, setHelpOpen, member } = useHeirloom();
  const [contacts, setContacts] = useState<HelpResource[]>(snapshot.help.other ?? []);
  const [logged, setLogged] = useState<"live" | "snapshot" | null>(null);

  useEffect(() => {
    if (!helpOpen) return;
    let live = true;
    setLogged(null);
    escalate(member.id, "other")
      .then((r) => {
        if (!live) return;
        setContacts(r.contacts);
        setLogged(r.source);
      })
      .catch(() => live && setLogged("snapshot"));
    return () => {
      live = false;
    };
  }, [helpOpen, member.id]);

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Talk to a Person</DialogTitle>
          <DialogDescription>These services are free, confidential and do not sell anything.</DialogDescription>
        </DialogHeader>
        <ul className="divide-y divide-line border-y border-line">
          {contacts.map((h) => (
            <li key={h.name} className="py-3.5">
              {h.url ? (
                <a href={h.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-semibold">
                  {h.name} <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : (
                <span className="font-semibold">{h.name}</span>
              )}
              {h.what && <p className="text-[.9rem] text-muted">{h.what}</p>}
              {h.phone && <p className="num mt-0.5 text-[.9rem]">Call {h.phone}</p>}
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[.82rem] text-muted">
          {logged === "live"
            ? `Logged as a "talk to a person" request for ${member.name}.`
            : logged === "snapshot"
              ? "Offline: these services are always available, but this request was not logged."
              : " "}
        </p>
      </DialogContent>
    </Dialog>
  );
}
