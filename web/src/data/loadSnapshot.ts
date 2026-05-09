import snapshotData from "./snapshot.json";
import type { SnapshotData, SnapshotState, StateColor } from "../types";

const SNAPSHOT_STATES: readonly SnapshotState[] = [
  "recovered",
  "cleared",
  "caution",
  "deload",
  "autonomic-recovery-leading",
  "peripheral-strain",
  "illness-risk",
  "accumulating-fatigue",
  "insufficient_data",
];

const STATE_COLORS: readonly StateColor[] = [
  "green",
  "amber",
  "red",
  "blue",
  "purple",
  "rose",
];

const INTERVENTION_CATEGORIES = [
  "sleep",
  "training",
  "recovery",
  "nutrition",
] as const;

const INTERVENTION_IMPACTS = ["HIGH", "MED", "LOW"] as const;

const DATA_SOURCES = ["whoop", "amazfit", "strava", "jefit", "bloodwork"] as const;

const STREAM_STATUSES = ["fresh", "stale", "old", "missing"] as const;

const NLR_HRV_TIERS = ["green", "caution", "deload", "unknown"] as const;

const SRI_TIERS = ["irregular", "moderate", "high", "unknown"] as const;

function isObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

function isString(x: unknown): x is string {
  return typeof x === "string";
}

function isNumber(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

function isBoolean(x: unknown): x is boolean {
  return typeof x === "boolean";
}

function enumError(
  errs: string[],
  basePath: string,
  value: unknown,
  allowed: readonly string[],
  label = "value",
): void {
  if (typeof value !== "string" || !allowed.includes(value)) {
    errs.push(
      `${basePath}${label}: expected one of ${allowed.join(", ")}, got ${JSON.stringify(value)}`,
    );
  }
}

/** Every structural / semantic deviation from SnapshotData; empty array means OK. */
export function snapshotValidationErrors(snapshot: unknown): string[] {
  const errs: string[] = [];

  if (!isObject(snapshot)) {
    return ["snapshot: expected non-null object"];
  }

  const p = "";

  enumError(errs, p, snapshot.state, SNAPSHOT_STATES, "state");
  const stateStr = snapshot.state;

  if (!isNumber(snapshot.score)) errs.push(`${p}score: expected finite number`);

  if (snapshot.todayScoreDisplay !== undefined) {
    if (!isString(snapshot.todayScoreDisplay))
      errs.push(`${p}todayScoreDisplay: expected string or omitted`);
    else if (
      stateStr === "insufficient_data" &&
      snapshot.todayScoreDisplay.trim() === ""
    ) {
      errs.push(
        `${p}todayScoreDisplay: insufficient_data requires a non-empty display string`,
      );
    }
  }

  if (stateStr === "insufficient_data" && snapshot.todayScoreDisplay === undefined) {
    errs.push(`${p}todayScoreDisplay: required when state is insufficient_data`);
  }

  const td = snapshot.todayDelta;
  if (!isObject(td)) errs.push(`${p}todayDelta: expected object`);
  else {
    if (!isNumber(td.value))
      errs.push(`${p}todayDelta.value: expected finite number`);
    if (td.unit !== undefined && !isString(td.unit))
      errs.push(`${p}todayDelta.unit: expected string or omitted`);
    if (td.vs !== undefined && !isString(td.vs))
      errs.push(`${p}todayDelta.vs: expected string or omitted`);
  }

  if (!isString(snapshot.subline)) errs.push(`${p}subline: expected string`);
  if (!isString(snapshot.action)) errs.push(`${p}action: expected string`);
  if (snapshot.todayReasoning !== undefined && !isString(snapshot.todayReasoning)) {
    errs.push(`${p}todayReasoning: expected string or omitted`);
  }

  /* monthlyContext */
  const mc = snapshot.monthlyContext;
  const mcPath = "monthlyContext";
  if (!isObject(mc)) errs.push(`${mcPath}: expected object`);
  else {
    const readiness = mc.readiness;
    if (!isObject(readiness)) errs.push(`${mcPath}.readiness: expected object`);
    else {
      if (!isNumber(readiness.score))
        errs.push(`${mcPath}.readiness.score: expected finite number`);
      if (!isNumber(readiness.vsLastMonth))
        errs.push(`${mcPath}.readiness.vsLastMonth: expected finite number`);
      if (!isString(readiness.windowLabel))
        errs.push(`${mcPath}.readiness.windowLabel: expected string`);
      if (!isString(readiness.meaning))
        errs.push(`${mcPath}.readiness.meaning: expected string`);
      if (readiness.reasoning !== undefined && !isString(readiness.reasoning))
        errs.push(`${mcPath}.readiness.reasoning: expected string or omitted`);
    }
    const bio = mc.bioAge;
    if (!isObject(bio)) errs.push(`${mcPath}.bioAge: expected object`);
    else {
      if (!isNumber(bio.years)) errs.push(`${mcPath}.bioAge.years: expected finite number`);
      if (!isNumber(bio.chronologicalYears))
        errs.push(`${mcPath}.bioAge.chronologicalYears: expected finite number`);
      if (!isString(bio.meaning)) errs.push(`${mcPath}.bioAge.meaning: expected string`);
      if (bio.reasoning !== undefined && !isString(bio.reasoning))
        errs.push(`${mcPath}.bioAge.reasoning: expected string or omitted`);
      const br = bio.breakdown;
      if (br !== undefined) {
        if (!Array.isArray(br))
          errs.push(`${mcPath}.bioAge.breakdown: expected array or omitted`);
        else {
          br.forEach((row, i) => {
            const bp = `${mcPath}.bioAge.breakdown[${i}]`;
            if (!isObject(row)) {
              errs.push(`${bp}: expected object`);
              return;
            }
            if (!isString(row.name)) errs.push(`${bp}.name: expected string`);
            if (!isNumber(row.pullYears))
              errs.push(`${bp}.pullYears: expected finite number`);
            if (!isNumber(row.weightPct))
              errs.push(`${bp}.weightPct: expected finite number`);
            if (!isString(row.detail)) errs.push(`${bp}.detail: expected string`);
            enumError(errs, `${bp}.`, row.state, STATE_COLORS, "state");
          });
        }
      }
    }
  }

  /* monthlyTrajectory */
  const mt = snapshot.monthlyTrajectory;
  const mtPath = "monthlyTrajectory";
  if (!isObject(mt)) errs.push(`${mtPath}: expected object`);
  else {
    if (!isString(mt.month)) errs.push(`${mtPath}.month: expected string`);
    if (!(mt.todayDayOfMonth === null || isNumber(mt.todayDayOfMonth)))
      errs.push(`${mtPath}.todayDayOfMonth: expected finite number or null`);
    const days = mt.days;
    if (!Array.isArray(days))
      errs.push(`${mtPath}.days: expected array`);
    else {
      days.forEach((d, i) => {
        const dp = `${mtPath}.days[${i}]`;
        if (!isObject(d)) {
          errs.push(`${dp}: expected object`);
          return;
        }
        enumError(errs, `${dp}.`, d.state, SNAPSHOT_STATES, "state");
        if (!isNumber(d.score)) errs.push(`${dp}.score: expected finite number`);
      });
    }
  }

  /* monthlyHistory */
  const mh = snapshot.monthlyHistory;
  if (!Array.isArray(mh)) errs.push(`${p}monthlyHistory: expected array`);
  else {
    mh.forEach((row, i) => {
      const hp = `${p}monthlyHistory[${i}]`;
      if (!isObject(row)) {
        errs.push(`${hp}: expected object`);
        return;
      }
      if (!isString(row.month)) errs.push(`${hp}.month: expected string`);
      if (!isNumber(row.score)) errs.push(`${hp}.score: expected finite number`);
    });

    const readinessScore = isObject(snapshot.monthlyContext)
      ? (snapshot.monthlyContext as Record<string, unknown>).readiness
      : undefined;
    const rs =
      readinessScore !== undefined &&
      isObject(readinessScore) &&
      isNumber((readinessScore as Record<string, unknown>).score)
        ? (readinessScore as { score: number }).score
        : undefined;

    if (mh.length > 0 && rs !== undefined) {
      const last = mh[mh.length - 1];
      if (isObject(last) && last.score !== rs) {
        errs.push(
          `${p}monthlyHistory[last].score (${last.score}) must equal monthlyContext.readiness.score (${rs})`,
        );
      }
    }
  }

  /* sevenDayState */
  const s7 = snapshot.sevenDayState;
  if (!Array.isArray(s7)) errs.push(`${p}sevenDayState: expected array`);
  else {
    if (s7.length !== 7)
      errs.push(`${p}sevenDayState: expected length 7, got ${s7.length}`);
    s7.forEach((st, i) => {
      enumError(errs, `${p}sevenDayState[${i}].`, st, SNAPSHOT_STATES, "state");
    });
  }

  /* secondaryReadouts */
  const sec = snapshot.secondaryReadouts;
  if (!Array.isArray(sec))
    errs.push(`${p}secondaryReadouts: expected array`);
  else {
    sec.forEach((r, i) => {
      const rp = `${p}secondaryReadouts[${i}]`;
      if (!isObject(r)) {
        errs.push(`${rp}: expected object`);
        return;
      }
      if (!isString(r.label)) errs.push(`${rp}.label: expected string`);
      if (!isString(r.value)) errs.push(`${rp}.value: expected string`);
      if (!isString(r.note)) errs.push(`${rp}.note: expected string`);
      enumError(errs, `${rp}.`, r.state, STATE_COLORS, "state");
    });
  }

  /* streams */
  const streams = snapshot.streams;
  if (!Array.isArray(streams)) errs.push(`${p}streams: expected array`);
  else {
    streams.forEach((s, i) => {
      const sp = `${p}streams[${i}]`;
      if (!isObject(s)) {
        errs.push(`${sp}: expected object`);
        return;
      }
      enumError(errs, `${sp}.`, s.source, DATA_SOURCES, "source");
      if (!isString(s.label)) errs.push(`${sp}.label: expected string`);
      enumError(errs, `${sp}.`, s.status, STREAM_STATUSES, "status");
      if (!isString(s.synced)) errs.push(`${sp}.synced: expected string`);
    });
  }

  /* flagship */
  const fs = snapshot.flagship;
  if (!isObject(fs)) errs.push(`${p}flagship: expected object`);
  else {
    const nlr = fs.nlrHrv;
    const nlrPath = `${p}flagship.nlrHrv`;
    if (!isObject(nlr)) errs.push(`${nlrPath}: expected object`);
    else {
      if (!isNumber(nlr.score)) errs.push(`${nlrPath}.score: expected finite number`);
      enumError(errs, `${nlrPath}.`, nlr.tier, NLR_HRV_TIERS, "tier");
      if (nlr.displayScore !== undefined && !isString(nlr.displayScore))
        errs.push(`${nlrPath}.displayScore: expected string or omitted`);
      if (
        Array.isArray(nlr.sparkline) &&
        !(nlr.sparkline.every((x) => isNumber(x)))
      )
        errs.push(`${nlrPath}.sparkline: expected number[]`);
      else if (!Array.isArray(nlr.sparkline))
        errs.push(`${nlrPath}.sparkline: expected array`);
      if (!isNumber(nlr.dataAgeDays))
        errs.push(`${nlrPath}.dataAgeDays: expected finite number`);
      const nd = nlr.delta;
      if (nd !== undefined) {
        if (!isObject(nd)) errs.push(`${nlrPath}.delta: expected object or omitted`);
        else {
          if (!isNumber(nd.value))
            errs.push(`${nlrPath}.delta.value: expected finite number`);
          if (nd.unit !== undefined && !isString(nd.unit))
            errs.push(`${nlrPath}.delta.unit: expected string or omitted`);
          if (nd.vs !== undefined && !isString(nd.vs))
            errs.push(`${nlrPath}.delta.vs: expected string or omitted`);
        }
      }
      if (nlr.reasoning !== undefined && !isString(nlr.reasoning))
        errs.push(`${nlrPath}.reasoning: expected string or omitted`);
    }

    const sri = fs.sri;
    const sriPath = `${p}flagship.sri`;
    if (!isObject(sri)) errs.push(`${sriPath}: expected object`);
    else {
      if (!isNumber(sri.score)) errs.push(`${sriPath}.score: expected finite number`);
      enumError(errs, `${sriPath}.`, sri.tier, SRI_TIERS, "tier");
      if (sri.displayScore !== undefined && !isString(sri.displayScore))
        errs.push(`${sriPath}.displayScore: expected string or omitted`);
      if (
        Array.isArray(sri.sparkline) &&
        !(sri.sparkline.every((x) => isNumber(x)))
      )
        errs.push(`${sriPath}.sparkline: expected number[]`);
      else if (!Array.isArray(sri.sparkline))
        errs.push(`${sriPath}.sparkline: expected array`);
      if (!isNumber(sri.windowDays))
        errs.push(`${sriPath}.windowDays: expected finite number`);
      const sd = sri.delta;
      if (sd !== undefined) {
        if (!isObject(sd)) errs.push(`${sriPath}.delta: expected object or omitted`);
        else {
          if (!isNumber(sd.value))
            errs.push(`${sriPath}.delta.value: expected finite number`);
          if (sd.unit !== undefined && !isString(sd.unit))
            errs.push(`${sriPath}.delta.unit: expected string or omitted`);
          if (sd.vs !== undefined && !isString(sd.vs))
            errs.push(`${sriPath}.delta.vs: expected string or omitted`);
        }
      }
      if (sri.reasoning !== undefined && !isString(sri.reasoning))
        errs.push(`${sriPath}.reasoning: expected string or omitted`);
    }

    const dec = fs.decoupling;
    const decPath = `${p}flagship.decoupling`;
    if (!isObject(dec)) errs.push(`${decPath}: expected object`);
    else {
      if (!isNumber(dec.zscore)) errs.push(`${decPath}.zscore: expected finite number`);
      if (!isString(dec.tier)) errs.push(`${decPath}.tier: expected non-empty string`);
      if (
        Array.isArray(dec.sparkline) &&
        !(dec.sparkline.every((x) => isNumber(x)))
      )
        errs.push(`${decPath}.sparkline: expected number[]`);
      else if (!Array.isArray(dec.sparkline))
        errs.push(`${decPath}.sparkline: expected array`);
      if (!isNumber(dec.windowDays))
        errs.push(`${decPath}.windowDays: expected finite number`);
      const dd = dec.delta;
      if (dd !== undefined) {
        if (!isObject(dd)) errs.push(`${decPath}.delta: expected object or omitted`);
        else {
          if (!isNumber(dd.value))
            errs.push(`${decPath}.delta.value: expected finite number`);
          if (dd.unit !== undefined && !isString(dd.unit))
            errs.push(`${decPath}.delta.unit: expected string or omitted`);
          if (dd.vs !== undefined && !isString(dd.vs))
            errs.push(`${decPath}.delta.vs: expected string or omitted`);
        }
      }
      if (dec.displayZscore !== undefined && !isString(dec.displayZscore))
        errs.push(`${decPath}.displayZscore: expected string or omitted`);
      if (dec.reasoning !== undefined && !isString(dec.reasoning))
        errs.push(`${decPath}.reasoning: expected string or omitted`);
    }
  }

  /* divergence */
  const div = snapshot.divergence;
  const divPath = `${p}divergence`;
  if (!isObject(div)) errs.push(`${divPath}: expected object`);
  else {
    if (!isBoolean(div.triggered)) errs.push(`${divPath}.triggered: expected boolean`);
    const optStr = (
      field: keyof typeof div,
      pathSuffix: string,
    ) => {
      const v = div[field];
      if (v !== undefined && !isString(v))
        errs.push(`${divPath}.${pathSuffix}: expected string or omitted`);
    };
    optStr("pattern", "pattern");
    optStr("interpretation", "interpretation");
    optStr("skillRef", "skillRef");
    optStr("reasoning", "reasoning");

    const drv = div.drivers;
    if (drv !== undefined) {
      if (!Array.isArray(drv))
        errs.push(`${divPath}.drivers: expected array or omitted`);
      else {
        drv.forEach((d, i) => {
          const dp = `${divPath}.drivers[${i}]`;
          if (!isObject(d)) {
            errs.push(`${dp}: expected object`);
            return;
          }
          if (!isString(d.signal)) errs.push(`${dp}.signal: expected string`);
          if (!isString(d.value)) errs.push(`${dp}.value: expected string`);
          if (!isString(d.note)) errs.push(`${dp}.note: expected string`);
          enumError(errs, `${dp}.`, d.state, STATE_COLORS, "state");
        });
      }
    }

    const q = div.question;
    if (q !== undefined) {
      if (!isObject(q))
        errs.push(`${divPath}.question: expected object or omitted`);
      else {
        if (!isString(q.prompt)) errs.push(`${divPath}.question.prompt: expected string`);
        if (!Array.isArray(q.options))
          errs.push(`${divPath}.question.options: expected array`);
        else {
          q.options.forEach((opt, i) => {
            const op = `${divPath}.question.options[${i}]`;
            if (!isObject(opt)) {
              errs.push(`${op}: expected object`);
              return;
            }
            if (!isString(opt.id)) errs.push(`${op}.id: expected string`);
            if (!isString(opt.label)) errs.push(`${op}.label: expected string`);
            const rsp = opt.response;
            if (!isObject(rsp)) errs.push(`${op}.response: expected object`);
            else {
              if (!isString(rsp.headline))
                errs.push(`${op}.response.headline: expected string`);
              if (
                rsp.confidenceTransition !== undefined &&
                !isString(rsp.confidenceTransition)
              )
                errs.push(`${op}.response.confidenceTransition: expected string or omitted`);
              const acts = rsp.actions;
              if (!Array.isArray(acts))
                errs.push(`${op}.response.actions: expected array`);
              else if (!(acts.every((a) => isString(a))))
                errs.push(`${op}.response.actions: expected string[]`);
            }
          });
        }
      }
    }
  }

  /* interventions */
  const inv = snapshot.interventions;
  if (!Array.isArray(inv)) errs.push(`${p}interventions: expected array`);
  else {
    inv.forEach((iv, i) => {
      const ip = `${p}interventions[${i}]`;
      if (!isObject(iv)) {
        errs.push(`${ip}: expected object`);
        return;
      }
      if (!isString(iv.action)) errs.push(`${ip}.action: expected string`);
      if (!isNumber(iv.effort) || !Number.isInteger(iv.effort)) {
        errs.push(`${ip}.effort: expected integer`);
      } else if (iv.effort < 1 || iv.effort > 5) {
        errs.push(`${ip}.effort: expected 1–5 inclusive, got ${iv.effort}`);
      }
      enumError(errs, `${ip}.`, iv.impact, INTERVENTION_IMPACTS, "impact");
      enumError(errs, `${ip}.`, iv.category, INTERVENTION_CATEGORIES, "category");
      if (!isString(iv.why)) errs.push(`${ip}.why: expected string`);
      if (!isString(iv.skillRef)) errs.push(`${ip}.skillRef: expected string`);
      if (iv.shortcut !== undefined && !isString(iv.shortcut))
        errs.push(`${ip}.shortcut: expected string or omitted`);
      const pc = iv.projectedComposite;
      if (pc !== undefined) {
        if (!isObject(pc))
          errs.push(`${ip}.projectedComposite: expected object or omitted`);
        else {
          if (!isString(pc.value))
            errs.push(`${ip}.projectedComposite.value: expected string`);
          if (!isString(pc.on)) errs.push(`${ip}.projectedComposite.on: expected string`);
        }
      }
      const pb = iv.projectedBioAge;
      if (pb !== undefined) {
        if (!isObject(pb))
          errs.push(`${ip}.projectedBioAge: expected object or omitted`);
        else {
          if (!isString(pb.value))
            errs.push(`${ip}.projectedBioAge.value: expected string`);
          if (!isString(pb.on)) errs.push(`${ip}.projectedBioAge.on: expected string`);
        }
      }
    });
  }

  return errs;
}

export function loadSnapshot(): SnapshotData {
  const errs = snapshotValidationErrors(snapshotData);
  if (errs.length) {
    throw new Error(
      ["Snapshot JSON validation failed:", ...errs.map((e) => `  · ${e}`)].join("\n"),
    );
  }
  return snapshotData as SnapshotData;
}
