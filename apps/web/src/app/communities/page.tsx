import Link from "next/link";
import { Landmark } from "lucide-react";
import { Panel } from "@/components/panel";

const communities = [
  {
    slug: "air-quality",
    name: "Air Quality",
    scope: "Statutes, regulations, notices, and data issues tied to Colorado air programs.",
    tags: ["environment", "public-health", "CDPHE_AQCC"]
  },
  {
    slug: "manufacturing",
    name: "Manufacturing",
    scope: "Compliance obligations and source-backed impact reports for manufacturing sectors.",
    tags: ["31-33", "permits", "reporting"]
  }
];

export default function CommunitiesPage() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Communities</p>
          <h1>Topic spaces generated from legal objects and ontology tags.</h1>
          <p className="lede">
            Communities organize source-backed work around agencies, topics, and regulated domains.
          </p>
        </div>
      </header>

      <Panel title="Community Index" icon={<Landmark className="icon" aria-hidden="true" />}>
        <div className="row-list">
          {communities.map((community) => (
            <article className="row-item" key={community.slug}>
              <Link className="search-result-title" href={`/communities/${community.slug}`}>
                {community.name}
              </Link>
              <p className="lede">{community.scope}</p>
              <div className="badge-row">
                {community.tags.map((tag) => (
                  <span className="badge" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
