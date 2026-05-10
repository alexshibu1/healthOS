import { useState } from "react";
import { Nav } from "./components/Nav";
import { KPICards } from "./components/KPICards";
import { BioAgeBreakdown } from "./components/BioAgeBreakdown";
import { SecondaryReadouts } from "./components/SecondaryReadouts";
import { FlagshipCards } from "./components/FlagshipCards";
import { DivergenceStrip } from "./components/DivergenceStrip";
import { Interventions } from "./components/Interventions";
import { LLMHandoff } from "./components/LLMHandoff";
import { SectionDivider } from "./components/SectionDivider";
import { Disclaimer } from "./components/Disclaimer";
import { Landing } from "./components/Landing";
import { UploadDialog } from "./components/UploadDialog";
import promptText from "./data/llm_prompt.txt?raw";
import { STATE_TO_COLOR } from "./lib/stateColors";
import { useHealthBootstrap } from "./hooks/useHealthBootstrap";
import { loadDemoSnapshot } from "./data/loadSnapshot";
import { getApiBaseUrl } from "./lib/apiBase";
import type { SnapshotData } from "./types";

/* ---------------------------------------------------------------- *
 * App — landing vs dashboard                                        *
 * ---------------------------------------------------------------- */

function Dashboard({
  data,
  onRequestUpload,
}: {
  data: SnapshotData;
  onRequestUpload?: () => void;
}) {
  const accentColor = STATE_TO_COLOR[data.state];

  const divergenceVisible = data.divergence.triggered;
  const signalsNumeral = divergenceVisible ? "III" : "II";
  const leversNumeral = divergenceVisible ? "IV" : "III";
  const llmNumeral = divergenceVisible ? "V" : "IV";

  return (
    <div className="min-h-screen text-ink">
      <Nav
        streams={data.streams}
        trailingActions={
          onRequestUpload ? (
            <button
              type="button"
              onClick={onRequestUpload}
              className="border border-paper-divider bg-paper px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-ink shadow-sm transition hover:border-ink/30 hover:bg-paper-tinted"
            >
              Upload
            </button>
          ) : undefined
        }
      />
      <main className="space-y-4 pb-12 lg:space-y-6">
        <SectionDivider numeral="I" title="Month at a glance" />
        <KPICards
          state={data.state}
          headlineInsufficient={data.state === "insufficient_data"}
          todayScore={data.score}
          todayScoreDisplay={data.todayScoreDisplay}
          todayDelta={data.todayDelta}
          subline={data.subline}
          action={data.action}
          todayReasoning={data.todayReasoning}
          monthlyContext={data.monthlyContext}
          monthlyTrajectory={data.monthlyTrajectory}
          monthlyHistory={data.monthlyHistory}
        />
        <BioAgeBreakdown bioAge={data.monthlyContext.bioAge} />
        <SecondaryReadouts readouts={data.secondaryReadouts} />

        {divergenceVisible && (
          <>
            <SectionDivider numeral="II" title="What's Diverging" />
            <DivergenceStrip
              divergence={data.divergence}
              accentColor={accentColor}
            />
          </>
        )}

        <SectionDivider
          numeral={signalsNumeral}
          title="The Signals"
          annotation="NLR×HRV · SRI · Decoupling"
        />
        <FlagshipCards
          nlrHrv={data.flagship.nlrHrv}
          sri={data.flagship.sri}
          decoupling={data.flagship.decoupling}
        />

        <SectionDivider
          numeral={leversNumeral}
          title="The Three Levers"
          annotation="ranked by 80/20 impact"
        />
        <Interventions interventions={data.interventions} />

        <LLMHandoff promptText={promptText} numeral={llmNumeral} />

        <Disclaimer />
      </main>
    </div>
  );
}

function App() {
  const { mode, snapshot: apiSnapshot } = useHealthBootstrap();
  const [manualDashboard, setManualDashboard] = useState<SnapshotData | null>(
    null,
  );
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

  const dashboardData = manualDashboard ?? apiSnapshot;

  const applyDemoSnapshot = () => {
    const d = loadDemoSnapshot();
    if (d) {
      setManualDashboard(d);
    }
  };

  if (mode === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center font-mono text-[11px] uppercase tracking-[0.2em] text-ink-muted">
        Loading…
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <>
        <Landing
          onOpenUpload={() => setUploadDialogOpen(true)}
          onUseDemo={applyDemoSnapshot}
        />
        <UploadDialog
          open={uploadDialogOpen}
          onOpenChange={setUploadDialogOpen}
          apiBase={getApiBaseUrl()}
          onSkipDemo={applyDemoSnapshot}
        />
      </>
    );
  }

  return (
    <>
      <Dashboard
        data={dashboardData}
        onRequestUpload={() => setUploadDialogOpen(true)}
      />
      <UploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        apiBase={getApiBaseUrl()}
        onSkipDemo={applyDemoSnapshot}
      />
    </>
  );
}

export default App;
