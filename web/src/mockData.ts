import type { SnapshotData } from "./types";

// Mock data for UI development.
// Shape matches src/score/specs/composite-spec.md (when written) +
// the SnapshotData interface defined for the snapshot page.
// Numbers are illustrative only; real values come from the scoring layer.

export const mockSnapshot: SnapshotData = {
  state: "autonomic-recovery-leading",
  score: 68,
  todayDelta: { value: 4, unit: "pts", vs: "yesterday" },
  // The Today card shows ONE short sentence by default — directive +
  // bridge — and pushes the longer explanation into the ⓘ expander, so
  // the layered-disclosure pattern is preserved on the secondary widget
  // too. The verbose original lives in todayReasoning below.
  subline: "Nervous system recovered; inflammation hasn't. Hold Z2.",
  action: "Hold today's training to Zone 2 only.",

  todayReasoning:
    "Your composite reads 68, +4 vs yesterday, but well below the 80+ green band. The reason your three flagships disagree: NLR×HRV at 1.68 (deload band) and aerobic decoupling at +0.4σ are both flagging strain, while SRI at 74 sits in the moderate band. The state name 'Autonomic Recovery Leading' captures that asymmetry — your wearable side (HRV ~+6% above 7-day baseline) is recovering ahead of your inflammatory side (NLR last measured at 5.37, 47 days ago). The composite has already been downweighted by the post-illness staleness multiplier; that's why it reads 68 and not closer to 78.",

  monthlyContext: {
    readiness: {
      score: 64,
      vsLastMonth: 3,
      windowLabel: "April 1 – April 30",
      meaning:
        "Steady caution band, trending up as inflammation cleared late in the month.",
      reasoning:
        "April averaged 64 — middle of the caution band, +3 vs March. The trend was up as the post-food-poisoning inflammation resolved late month. To break into the 75+ green band you'd need 5+ consecutive days with NLR×HRV under 1.0 and SRI ≥ 80; right now you have neither. Direction is right, pace is slow.",
    },
    bioAge: {
      years: 24.1,
      chronologicalYears: 21,
      meaning:
        "Sleep regularity is dragging this number more than HRV or training does.",
      reasoning:
        "24.1y proxy vs chronological 21y — a 3.1-year gap. Sleep regularity is the dominant lever: your SRI is 74 against the 80+ target. Closing that one metric alone would shrink the gap by roughly 1.5 years. HRV trend and resting HR are already tracking your chronological age — SRI is the bottleneck. Pulling sleep onset before 11pm is the single biggest move on this number.",
      // Three transparent contributors. Their pullYears sum (≈3.1) ≈ the
      // observed years − chronological gap. This is the proof that the
      // bio-age number isn't a black box.
      breakdown: [
        {
          name: "Sleep Regularity",
          pullYears: 1.8,
          weightPct: 58,
          detail: "SRI 74 vs 80+ target · σ ≈ 47 min onset",
          state: "amber",
        },
        {
          name: "HRV trend",
          pullYears: 0.9,
          weightPct: 29,
          detail: "30d trend −0.4σ vs age-21 cohort baseline",
          state: "amber",
        },
        {
          name: "Resting HR baseline",
          pullYears: 0.4,
          weightPct: 13,
          detail: "62 bpm vs cohort 58 bpm · drift +2 bpm in 30d",
          state: "amber",
        },
      ],
    },
  },

  // 30 daily states + scores for April. Order: oldest (April 1) → newest
  // (April 30). The arc tells the food-poisoning storyline:
  //   - days 1-5:   strong start, brief peak (cleared 84, 86)
  //   - days 6-9:   slowdown as inflammation builds
  //   - days 10-11: dip (illness-risk 36, 38) — the actual sick days
  //   - days 12-20: oscillating climb out of deload
  //   - days 21-28: caution band stabilizing
  //   - days 29-30: autonomic-recovery-leading — today
  // Mean ≈ 63.5 ≈ headline 64 (slight gap explained by completeness
  // weighting per composite-spec §3).
  monthlyTrajectory: {
    month: "April 2026",
    days: [
      { state: "caution", score: 66 },
      { state: "caution", score: 68 },
      { state: "cleared", score: 84 },
      { state: "cleared", score: 86 },
      { state: "caution", score: 70 },
      { state: "deload", score: 60 },
      { state: "deload", score: 53 },
      { state: "deload", score: 50 },
      { state: "deload", score: 48 },
      { state: "illness-risk", score: 36 },
      { state: "illness-risk", score: 38 },
      { state: "deload", score: 55 },
      { state: "deload", score: 54 },
      { state: "deload", score: 62 },
      { state: "deload", score: 64 },
      { state: "caution", score: 65 },
      { state: "caution", score: 68 },
      { state: "caution", score: 70 },
      { state: "deload", score: 62 },
      { state: "deload", score: 56 },
      { state: "caution", score: 72 },
      { state: "caution", score: 73 },
      { state: "caution", score: 75 },
      { state: "deload", score: 64 },
      { state: "deload", score: 58 },
      { state: "caution", score: 72 },
      { state: "caution", score: 74 },
      { state: "deload", score: 64 },
      { state: "autonomic-recovery-leading", score: 67 },
      { state: "autonomic-recovery-leading", score: 68 },
    ],
    todayDayOfMonth: 30,
  },

  // 6-month rolling history. Same arc as the 30-day strip but at month
  // resolution: stable autumn → winter softening → February-March illness
  // floor → April recovery. The last entry's score == this month's score.
  monthlyHistory: [
    { month: "Nov 2025", score: 71 },
    { month: "Dec 2025", score: 73 },
    { month: "Jan 2026", score: 70 },
    { month: "Feb 2026", score: 65 },
    { month: "Mar 2026", score: 61 },
    { month: "Apr 2026", score: 64 },
  ],

  // 4 derived signals that complement the three primary signals. Single-line,
  // scan-only — no expander. State color tints them so the user can read
  // direction at a glance.
  secondaryReadouts: [
    {
      label: "HRV 30d",
      value: "+4 ms",
      note: "trending up vs March",
      state: "green",
    },
    {
      label: "RHR baseline",
      value: "+2 bpm",
      note: "drifted up in last 30d",
      state: "amber",
    },
    {
      label: "Sleep debt",
      value: "−3.2 h",
      note: "vs 7.5h target, last 7d",
      state: "amber",
    },
    // Z2 ratio replaces Monocytes here — monocytes already appear as a
    // divergence driver, and marginalia should be *complementary* to the
    // story above it, not a duplicate. Z2 ratio cross-references the
    // decoupling signal with a different lens (volume vs efficiency).
    {
      label: "Z2 ratio",
      value: "38%",
      note: "vs 50% target, last 30d",
      state: "amber",
    },
  ],

  // Oldest → newest (today is the rightmost cell)
  sevenDayState: [
    "caution",
    "caution",
    "deload",
    "deload",
    "deload",
    "autonomic-recovery-leading",
    "autonomic-recovery-leading",
  ],

  streams: [
    { source: "amazfit", label: "AMAZFIT", status: "fresh", synced: "2h" },
    { source: "strava", label: "STRAVA", status: "fresh", synced: "6h" },
    { source: "jefit", label: "JEFIT", status: "stale", synced: "1d" },
    { source: "bloodwork", label: "BLOOD", status: "old", synced: "47d" },
  ],

  flagship: {
    nlrHrv: {
      score: 1.68,
      tier: "deload",
      sparkline: [
        1.42, 1.45, 1.51, 1.58, 1.63, 1.6, 1.55, 1.59, 1.66, 1.71, 1.74, 1.7,
        1.69, 1.68,
      ],
      dataAgeDays: 47,
      delta: { value: 0.12, unit: "", vs: "7d avg" },
      reasoning:
        "Your last NLR was 5.37, drawn 47 days ago during the food-poisoning panel — well above the 3.0 clinical-concern threshold. Your HRV is roughly +6% above its 7-day baseline (recovering — that's the lymphocyte arm of inflammation resolving). The composite 1.68 sits 12% above the 1.5 deload threshold, and because the CBC is between 30 and 60 days old the model applies a lab-age discount (confidence weighted to 0.85) until your next draw. Translation: the wearable side is genuinely improving, the blood side hasn't been re-measured. Get a fresh CBC before adding intensity — the score won't move out of deload until either NLR drops below 3.0 or you confirm the elevated reading was a transient post-illness spike.",
    },
    sri: {
      score: 74,
      tier: "moderate",
      sparkline: [70, 72, 71, 73, 75, 78, 80, 79, 76, 74, 72, 73, 74, 74],
      windowDays: 14,
      delta: { value: -2, unit: "pts", vs: "7d avg" },
      reasoning:
        "You're at 74 — 6 points below the 80+ high-regularity threshold where the Windred 2024 mortality-risk drop kicks in (UK Biobank, n=60,977). Your 14-day sparkline peaked at 80 on day 7 and has drifted back since — directionally going the wrong way. The driver is bedtime variance, not duration: σ ≈ 47 minutes on sleep onset is what's keeping you sub-80. Pull onset before 11pm and tighten the window to ±15 min, and you cross 80 inside two weeks. This is the single most movable lever on your bio-age proxy too.",
    },
    decoupling: {
      zscore: 0.4,
      tier: "caution",
      sparkline: [
        -0.2, -0.1, 0.0, 0.1, 0.0, -0.1, 0.1, 0.2, 0.3, 0.2, 0.3, 0.4, 0.5, 0.4,
        0.4, 0.3, 0.4, 0.5, 0.4, 0.4, 0.4,
      ],
      windowDays: 21,
      delta: { value: 0.3, unit: "σ", vs: "30d baseline" },
      reasoning:
        "+0.4σ — drifting band, not yet fraying (≥+1σ is the clinical flag, peak in your 21-session window is +0.5σ). Skill §3 flags 5+ consecutive days above baseline as an early warning; you've had 15 in a row. Your aerobic economy is genuinely slipping — the same Z2 pace is costing more heart rate. Heat, hydration, or residual post-illness fatigue are the usual culprits. Concrete check: is your Z2 HR running 5–8 bpm above your 30-day mean for the same pace? If yes, that's the leak.",
    },
  },

  divergence: {
    triggered: true,
    pattern: "HRV improving while NLR still elevated",
    interpretation:
      "Autonomic recovery preceding inflammatory resolution. Common post-illness window.",
    skillRef: "§1.2",
    reasoning:
      "This is your specific pattern. HRV trend has been positive for ~9 days — that's autonomic recovery, the lymphocyte arm responding. But the NLR on file is 5.37, above the 3.0 threshold and 47 days old. We can't see whether inflammation has cleared since the panel was drawn; we only know it hadn't on the day of the draw. Action implication: hold deload until either a fresh CBC shows NLR < 3.0, or 14+ days of stable HRV without symptoms passes (spec §4.1). The composite has already been downweighted to reflect this uncertainty — this strip is the explanation for why.",
    drivers: [
      {
        signal: "NLR",
        value: "5.37 (47 days old)",
        note: "above 3.0 clinical-concern threshold",
        state: "red",
      },
      {
        signal: "Monocytes",
        value: "1.2 ×10⁹/L (47d old)",
        note: "above 0.8 ref bound — post-illness flag",
        state: "red",
      },
      {
        signal: "HRV 7d trend",
        value: "+6% vs baseline",
        note: "lymphocyte arm recovering — wearable says go",
        state: "green",
      },
      {
        signal: "Aerobic decoupling",
        value: "+0.4σ, 15-day run above baseline",
        note: "Z2 economy slipping — confirms residual strain",
        state: "amber",
      },
    ],
    question: {
      prompt: "To firm up the reading, were you sick during this month?",
      options: [
        {
          id: "yes_food",
          label: "Yes — food poisoning",
          response: {
            headline: "Confirmed: post-food-poisoning window logged.",
            confidenceTransition: "0.78 → 0.91",
            actions: [
              "NLR 5.37 reinterpreted as resolution-lag rather than acute inflammation.",
              "Post-illness lock active until day 14 of recovery.",
              "Stale lab weighting stays in effect until your next blood draw.",
            ],
          },
        },
        {
          id: "yes_other",
          label: "Yes — other illness",
          response: {
            headline: "Confirmed: non-food illness window logged.",
            confidenceTransition: "0.78 → 0.86",
            actions: [
              "NLR treated with same calibration as a food-poisoning window.",
              "Post-illness lock active until day 14 of recovery.",
            ],
          },
        },
        {
          id: "no",
          label: "No, felt fine",
          response: {
            headline: "Logged: no illness reported this month.",
            confidenceTransition: "0.78 → 0.65",
            actions: [
              "NLR 5.37 now interpreted as residual concern, not resolution-lag.",
              "Recommended: fresh CBC within 7 days to resolve uncertainty.",
              "Composite downweighting deepens until clarity arrives.",
            ],
          },
        },
        {
          id: "unsure",
          label: "Unsure",
          response: {
            headline: "Logged: uncertain — continuing conservative interpretation.",
            confidenceTransition: "unchanged at 0.78",
            actions: [
              "Full NLR conservatism stays in place.",
              "A fresh blood panel is the only thing that resolves this.",
            ],
          },
        },
      ],
    },
  },

  // Each lever carries projected deltas on (a) the monthly composite and
  // (b) the bio-age gap, where applicable. This makes levers numerically
  // comparable, and ties the section back to the bio-age breakdown above —
  // the meta-loop the page would otherwise be missing.
  interventions: [
    {
      action: "Anchor sleep onset before 11pm",
      effort: 3,
      impact: "HIGH",
      category: "sleep",
      why: "SRI is unstable (σ ≈ 47 min over 14 days). Windred 2024 (UK Biobank, n=60,977) found SRI < 70 was associated with 20–48% higher all-cause mortality risk. Pulling onset earlier and tightening its variance is the single largest 80/20 lever you can move today.",
      skillRef: "§2.2",
      shortcut: "⌘1",
      // SRI is the dominant bio-age contributor (+1.8y of the +3.1y gap),
      // so this is the largest single bio-age lever on the page.
      projectedComposite: { value: "+6 pts", on: "April composite" },
      projectedBioAge: { value: "−1.4y", on: "bio-age gap" },
    },
    {
      action: "Cap all training at Zone 2 today",
      effort: 4,
      impact: "HIGH",
      category: "training",
      why: "NLR at 5.37 is materially above the 3.0 clinical-concern threshold. Kaniganti 2022 showed a single high-intensity session can transiently raise NLR by ~50%. Layering intensity on inflammation that hasn't cleared is the exact pattern that causes post-illness relapse (skill §1.2).",
      skillRef: "§1.2",
      shortcut: "⌘2",
      projectedComposite: { value: "+4 pts", on: "April composite" },
      // Z2 capping is preventative — it doesn't move the bio-age
      // contributors directly, so no bio-age projection here.
    },
    {
      action: "10-min walk 20 minutes after dinner",
      effort: 2,
      impact: "MED",
      category: "nutrition",
      why: "Random glucose 5.4 mmol/L is at the upper edge of normal. He et al. 2020 (PMC7228054) showed bedtime/duration variability tracks with insulin response; a brief post-meal walk dampens the postprandial peak without adding to today's training strain.",
      skillRef: "§1.5",
      shortcut: "⌘3",
      projectedComposite: { value: "+2 pts", on: "April composite" },
      projectedBioAge: { value: "−0.3y", on: "bio-age gap" },
    },
  ],
};
