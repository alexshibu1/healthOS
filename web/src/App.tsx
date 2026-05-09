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
import { loadSnapshot } from "./data/loadSnapshot";
import promptText from "./data/llm_prompt.txt?raw";
import { STATE_TO_COLOR } from "./lib/stateColors";

/* ---------------------------------------------------------------- *
 * App — page composition                                            *
 *                                                                   *
 * The page reads as numbered chapters (I–IV). Each chapter has        *
 * a single conceptual purpose:                                      *
 *                                                                   *
 *   I.  Month at a glance     the headline of the month + today    *
 *                            check-in + bio-age breakdown +       *
 *                            secondary readouts                    *
 *   II. What's Diverging     when signals disagree, why, and what *
 *                            we need to ask the user to be sure   *
 *   III. The Signals         the three primary metrics — NLR×HRV, *
 *                            SRI, aerobic decoupling              *
 *   IV. The Three Levers     the punchline: do these three things *
 *   V. Get recommendations   LLM handoff prompt from your snapshot *
 *                                                                   *
 * Section IV is intentionally placed last because it's the         *
 * payoff — every signal above exists to justify these three        *
 * actions.                                                          *
 * ---------------------------------------------------------------- */

function App() {
  const data = loadSnapshot();
  const accentColor = STATE_TO_COLOR[data.state];

  // Numerals shift if the optional Divergence chapter is hidden.
  const divergenceVisible = data.divergence.triggered;
  const signalsNumeral = divergenceVisible ? "III" : "II";
  const leversNumeral = divergenceVisible ? "IV" : "III";
  const llmNumeral = divergenceVisible ? "V" : "IV";

  return (
    <div className="min-h-screen text-ink">
      <Nav streams={data.streams} />
      <main className="space-y-4 pb-12 lg:space-y-6">
        {/* I. Month at a glance — month-as-hero + today + bio-age + readouts */}
        <SectionDivider
          numeral="I"
          title="Month at a glance"
        />
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

        {/* II. What's Diverging — only when triggered. */}
        {divergenceVisible && (
          <>
            <SectionDivider numeral="II" title="What's Diverging" />
            <DivergenceStrip
              divergence={data.divergence}
              accentColor={accentColor}
            />
          </>
        )}

        {/* III. The Signals — primary metric cards. */}
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

        {/* IV. The Three Levers — the payoff. */}
        <SectionDivider
          numeral={leversNumeral}
          title="The Three Levers"
          annotation="ranked by 80/20 impact"
        />
        <Interventions interventions={data.interventions} />

        {/* V. LLM handoff — deterministic prompt for external recommendations. */}
        <LLMHandoff promptText={promptText} numeral={llmNumeral} />

        <Disclaimer />
      </main>
    </div>
  );
}

export default App;
