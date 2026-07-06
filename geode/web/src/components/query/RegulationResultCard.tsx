import type { ReactElement } from "react";

import type { RegulationSearchResult } from "@/lib/search/types";

type RegulationResultCardProps = {
  personalized?: boolean;
  result: RegulationSearchResult;
  onOpen: (result: RegulationSearchResult) => void;
};

export function RegulationResultCard({
  personalized = false,
  result,
  onOpen,
}: RegulationResultCardProps): ReactElement {
  return (
    <button
      className={personalized ? "regulation-card is-personalized" : "regulation-card"}
      onClick={() => onOpen(result)}
      type="button"
    >
      <span className="regulation-card-index">{result.citation}</span>
      <span className="regulation-card-topline">
        <span>{personalized ? "Profile weighted" : "Corpus match"}</span>
        <span>
          {personalized ? "Profile weighted" : `${Math.round(result.score)} relevance`}
          {result.relationshipCount ? ` / ${result.relationshipCount} links` : ""}
        </span>
      </span>
      <span className="regulation-card-title">{result.title}</span>
      <span className="regulation-card-excerpt">{result.excerpt}</span>
      {result.matchReasons?.length ? (
        <span className="regulation-card-reasons">
          {result.matchReasons.slice(0, 3).map((reason) => (
            <span key={reason}>{reason}</span>
          ))}
        </span>
      ) : null}
      <span className="regulation-card-footer">
        <span className="regulation-card-source">Citation preview</span>
        <span className="regulation-card-action">{actionLabel(result)}</span>
      </span>
    </button>
  );
}

function actionLabel(result: RegulationSearchResult): string {
  if (result.layer === "01_Statutes_CRS") {
    return "Open statute";
  }

  if (result.layer === "02_Regulations_CCR") {
    return "Open regulation";
  }

  return "Open authority";
}
