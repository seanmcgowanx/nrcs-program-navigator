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

// Realistic advisor prompts describing a client operation in plain language.
// Each leans toward a different program so the examples cover the catalog.
export const EXAMPLE_PROMPTS: string[] = [
  "A client runs 180 acres of irrigated almonds in Stanislaus County, California and wants to cut water use.",
  "Rancher with 1,200 acres of native grazing land in Harding County, New Mexico, interested in rotational grazing support.",
  "Dairy operation in Tillamook County, Oregon looking to fund a waste storage facility and clean water.",
  "Landowner wants to place 60 acres of restored wetland into a long term easement.",
];
