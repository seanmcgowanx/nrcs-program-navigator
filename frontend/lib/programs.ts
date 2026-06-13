// The four in scope NRCS programs the agent reasons over. Used for the
// reference legend in the rail. Kept in sync with config.PROGRAMS on the
// backend.
export interface Program {
  code: string;
  name: string;
  blurb: string;
}

export const PROGRAMS: Program[] = [
  {
    code: "EQIP",
    name: "Environmental Quality Incentives",
    blurb: "Cost share for conservation practices on working land.",
  },
  {
    code: "CSP",
    name: "Conservation Stewardship",
    blurb: "Annual payments for maintaining and building on stewardship.",
  },
  {
    code: "ACEP",
    name: "Agricultural Conservation Easements",
    blurb: "Long term easements for wetlands and working land.",
  },
  {
    code: "RCPP",
    name: "Regional Conservation Partnership",
    blurb: "Partner led projects targeting regional priorities.",
  },
];

// Advisor prompts taken verbatim from the in scope evaluation set
// (src/nrcs_navigator/evaluation/datasets.py), chosen to span all four
// programs: EQIP (erosion), CSP (grazing), ACEP (easement), RCPP (partnership).
// Using the eval questions keeps the demo aligned with what the agent is graded
// on.
export const EXAMPLE_PROMPTS: string[] = [
  "I have a client with about 300 acres of corn and soybean cropland in Iowa. They're losing topsoil to sheet and rill erosion and want help addressing it. What programs fit?",
  "A client runs a cattle operation on 500 acres of grazing land in Texas. Their primary resource concern is degraded grazing land health (overgrazed pasture and poor forage), and they want to improve it with rotational grazing. What practices and payments could apply?",
  "My client in Louisiana owns 80 acres of wetland and wants to permanently protect it from future development through a conservation easement. Their primary resource concern is wetland habitat loss. What are their options and expected payouts?",
  "A group of landowners in the Chesapeake Bay watershed want to coordinate on a partnership led conservation project to improve water quality. Is there an NRCS program built for that kind of partnership effort?",
];
