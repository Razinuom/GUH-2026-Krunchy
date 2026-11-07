import { AnimatePresence } from "framer-motion";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation, Navigate } from "react-router-dom";
import About from "@/pages/About";
import ClaimCheck from "@/pages/ClaimCheck";
import Family from "@/pages/Family";
import Forecast from "@/pages/Forecast";
import Home from "@/pages/Home";
import TimeMachine from "@/pages/TimeMachine";

// the ElevenLabs voice SDK is large, so it only loads when the Voice Coach page opens
const VoiceCoach = lazy(() => import("@/pages/VoiceCoach"));

export function AppRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Home />} />
        <Route path="/family" element={<Family />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/time-machine" element={<TimeMachine />} />
        <Route
          path="/coach"
          element={
            <Suspense fallback={<p className="py-16 text-center text-muted">Loading the voice coach…</p>}>
              <VoiceCoach />
            </Suspense>
          }
        />
        <Route path="/claims" element={<ClaimCheck />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  );
}
