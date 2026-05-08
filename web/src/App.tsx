import { Nav } from "./components/Nav";
import { ContextStrip } from "./components/ContextStrip";
import { StateHero } from "./components/StateHero";
import { FlagshipCards } from "./components/FlagshipCards";
import { DivergenceStrip } from "./components/DivergenceStrip";
import { Interventions } from "./components/Interventions";
import { STATE_TO_COLOR } from "./lib/stateColors";
import { mockSnapshot } from "./mockData";

function App() {
  const data = mockSnapshot;
  const accentColor = STATE_TO_COLOR[data.state];

  return (
    <div className="min-h-screen bg-paper-tinted text-ink">
      <Nav />
      <main>
        <ContextStrip context={data.monthlyContext} />
        <StateHero
          state={data.state}
          score={data.score}
          subline={data.subline}
          action={data.action}
        />
        <FlagshipCards
          nlrHrv={data.flagship.nlrHrv}
          sri={data.flagship.sri}
          decoupling={data.flagship.decoupling}
        />
        <DivergenceStrip
          divergence={data.divergence}
          accentColor={accentColor}
        />
        <Interventions interventions={data.interventions} />
      </main>
    </div>
  );
}

export default App;
