import type { ReactElement } from "react";

import { RegulationsIndex } from "@/components/regulations/RegulationsIndex";
import {
  getRegulationCorpusStats,
  searchRegulations,
} from "@/lib/search/searchRegulations";

const STARTING_QUERY = "air quality";

export default function RegulationsPage(): ReactElement {
  const stats = getRegulationCorpusStats();
  const regulations = searchRegulations(STARTING_QUERY, 24).map((regulation) => ({
    ...regulation,
    body: "",
    excerpt: previewText(regulation.excerpt || regulation.body),
  }));

  return <RegulationsIndex regulations={regulations} stats={stats} />;
}

function previewText(value: string): string {
  const cleaned = value
    .replace(/^---[\s\S]*?---/u, "")
    .replace(/#+\s*/gu, "")
    .replace(/\s+/gu, " ")
    .trim();

  if (cleaned.length <= 220) {
    return cleaned;
  }

  return `${cleaned.slice(0, 217).trim()}...`;
}
