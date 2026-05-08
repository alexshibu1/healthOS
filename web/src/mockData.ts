import type { SnapshotData } from "./types";

// Mock data for UI development.
// Shape matches src/score/specs/composite-spec.md (when written) +
// the SnapshotData interface defined for the snapshot page.
// Numbers are illustrative only; real values come from the scoring layer.

export const mockSnapshot: SnapshotData = {
  state: "autonomic-recovery-leading",
  score: 68,
  subline:
    "Your nervous system has recovered, but blood markers from last month's food-poisoning episode haven't fully cleared yet. The wearable is more optimistic than the body actually is.",
  action: "Hold today's training to Zone 2 only.",

  monthlyContext: {
    readiness: {
      score: 64,
      vsLastMonth: 3,
      windowLabel: "April 1 – April 30",
      meaning:
        "Steady caution band, trending up as inflammation cleared late in the month.",
    },
    bioAge: {
      years: 24.1,
      chronologicalYears: 21,
      meaning:
        "Sleep regularity is dragging this number more than HRV or training does.",
    },
  },

  flagship: {
    nlrHrv: {
      score: 1.68,
      tier: "deload",
      sparkline: [
        1.42, 1.45, 1.51, 1.58, 1.63, 1.6, 1.55, 1.59, 1.66, 1.71, 1.74, 1.7,
        1.69, 1.68,
      ],
      dataAgeDays: 47,
    },
    sri: {
      score: 74,
      tier: "moderate",
      sparkline: [70, 72, 71, 73, 75, 78, 80, 79, 76, 74, 72, 73, 74, 74],
      windowDays: 14,
    },
    decoupling: {
      zscore: 0.4,
      tier: "caution",
      sparkline: [
        -0.2, -0.1, 0.0, 0.1, 0.0, -0.1, 0.1, 0.2, 0.3, 0.2, 0.3, 0.4, 0.5, 0.4,
        0.4, 0.3, 0.4, 0.5, 0.4, 0.4, 0.4,
      ],
      windowDays: 21,
    },
  },

  divergence: {
    triggered: true,
    pattern: "HRV improving while NLR still elevated",
    interpretation:
      "Autonomic recovery preceding inflammatory resolution. Common post-illness window.",
    skillRef: "§1.2",
  },

  interventions: [
    {
      action: "Anchor sleep onset before 11pm",
      effort: 3,
      impact: "HIGH",
      why: "SRI is unstable (σ ≈ 47 min over 14 days). Windred 2024 (UK Biobank, n=60,977) found SRI < 70 was associated with 20–48% higher all-cause mortality risk. Pulling onset earlier and tightening its variance is the single largest 80/20 lever you can move today.",
      skillRef: "§2.2",
    },
    {
      action: "Cap all training at Zone 2 today",
      effort: 4,
      impact: "HIGH",
      why: "NLR at 5.37 is materially above the 3.0 clinical-concern threshold. Kaniganti 2022 showed a single high-intensity session can transiently raise NLR by ~50%. Layering intensity on inflammation that hasn't cleared is the exact pattern that causes post-illness relapse (skill §1.2).",
      skillRef: "§1.2",
    },
    {
      action: "10-min walk 20 minutes after dinner",
      effort: 2,
      impact: "MED",
      why: "Random glucose 5.4 mmol/L is at the upper edge of normal. He et al. 2020 (PMC7228054) showed bedtime/duration variability tracks with insulin response; a brief post-meal walk dampens the postprandial peak without adding to today's training strain.",
      skillRef: "§1.5",
    },
  ],
};
