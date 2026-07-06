import { Filter, Search } from "lucide-react";
import { Panel } from "@/components/panel";
import { SearchResults } from "@/components/search-results";
import { searchCorpus } from "@/lib/data";

type SearchPageProps = {
  searchParams?: {
    q?: string;
  };
};

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const query = searchParams?.q ?? "";
  const results = await searchCorpus(query);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Search</p>
          <h1>Search official law separately from discussion.</h1>
          <p className="lede">
            Results preserve the boundary between indexed Geode records and community context.
          </p>
        </div>
      </header>

      <section className="panel hero-search panel-spacer">
        <form action="/search">
          <input
            className="search-large"
            defaultValue={query}
            name="q"
            placeholder="Citation, source text, agency, topic"
            type="search"
          />
          <button className="button primary" type="submit">
            <Search className="icon" aria-hidden="true" />
            Search
          </button>
        </form>
      </section>

      <div className="filter-bar" aria-label="Search filters">
        {["Law results", "Passages", "Agencies", "Rulemaking", "Discussions", "Open issues"].map(
          (filter) => (
            <span className="filter-chip" key={filter}>
              <Filter className="icon" aria-hidden="true" />
              {filter}
            </span>
          )
        )}
      </div>

      <Panel title={query ? `Results for "${query}"` : "Indexed Legal Objects"}>
        <SearchResults results={results} />
      </Panel>
    </div>
  );
}
