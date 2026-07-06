export type OnboardingRegulationSuggestion = {
  citation: string;
  excerpt: string;
  id: string;
  score: number;
  sourceUrl: string | null;
  title: string;
};

export type OnboardingAnalysis = {
  citations: string[];
  documentKind: string;
  industries: string[];
  jurisdiction: string;
  relatedRegulations: OnboardingRegulationSuggestion[];
  role: string;
  summary: string;
};

export type OnboardingParseResponse = {
  analysis: OnboardingAnalysis;
};
