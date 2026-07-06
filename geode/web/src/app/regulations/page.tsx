import type { ReactElement } from "react";

import { RegulationsIndex } from "@/components/regulations/RegulationsIndex";
import { searchRegulations } from "@/lib/search/searchRegulations";

const STARTING_QUERY = "air quality";

export default function RegulationsPage(): ReactElement {
  const regulations = searchRegulations(STARTING_QUERY, 24);

  return <RegulationsIndex regulations={regulations} />;
}
