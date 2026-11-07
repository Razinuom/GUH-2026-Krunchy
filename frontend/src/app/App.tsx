import { useEffect } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import { HelpDialog } from "@/components/HelpDialog";
import { TopBar } from "@/components/layout/TopBar";
import { HeirloomProvider, useHeirloom } from "@/state/HeirloomContext";
import { AppRoutes } from "./routes";

function Shell() {
  const { member } = useHeirloom();
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <>
      <a href="#main" className="sr-only left-4 top-2 z-50 rounded-lg bg-ink px-3 py-2 text-surface focus:not-sr-only focus:fixed">
        Skip to Content
      </a>
      <TopBar />
      <main
        id="main"
        data-gen={member.gen}
        className="mx-auto max-w-[1180px] [padding-inline:max(20px,env(safe-area-inset-left))]"
      >
        <AppRoutes />
      </main>
      <HelpDialog />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <HeirloomProvider>
        <Shell />
      </HeirloomProvider>
    </BrowserRouter>
  );
}
