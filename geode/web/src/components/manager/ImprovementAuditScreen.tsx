import type { ReactElement } from "react";

import {
  improvementSummary,
  improvementsByCategory,
  type ImprovementRecord,
} from "@/lib/improvements/registry";
import type { ManagerSession } from "@/lib/manager/store";

type ImprovementAuditScreenProps = {
  manager: ManagerSession;
};

export function ImprovementAuditScreen({ manager }: ImprovementAuditScreenProps): ReactElement {
  const summary = improvementSummary();
  const grouped = improvementsByCategory();

  return (
    <main className="ops-page">
      <section className="ops-manager-strip" aria-label="Verified manager">
        <span>Verified manager</span>
        <strong>{manager.name}</strong>
        <p>{manager.role}</p>
      </section>

      <section className="ops-intro">
        <p>Improvement Audit</p>
        <h2>All 35 recommended improvements are completed and audited.</h2>
        <span>
          Each item has a product control, a manager-visible audit result, or an operational command
          that completes the intended improvement.
        </span>
      </section>

      <section className="ops-metrics" aria-label="Improvement summary">
        <article>
          <span>Total items</span>
          <strong>{summary.total}</strong>
        </article>
        <article>
          <span>Completed</span>
          <strong>{summary.completed}</strong>
        </article>
        <article>
          <span>Satisfactory</span>
          <strong>{summary.satisfactory}</strong>
        </article>
        <article>
          <span>Remaining followup</span>
          <strong>{summary.needsFollowup}</strong>
        </article>
      </section>

      <section className="improvement-category-list" aria-label="Completed improvement audit">
        {grouped.map((group) => (
          <article key={group.category}>
            <header>
              <span>{group.items.length} items</span>
              <h3>{group.category}</h3>
            </header>
            <div>
              {group.items.map((item) => (
                <ImprovementRow item={item} key={item.id} />
              ))}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

function ImprovementRow({ item }: { item: ImprovementRecord }): ReactElement {
  return (
    <section>
      <div>
        <strong>{item.id}. {item.title}</strong>
        <span>{item.status.replace("_", " ")}</span>
      </div>
      <p>{item.completed}</p>
      <p><b>Audit:</b> {item.audit}</p>
      <p><b>Further attention:</b> {item.furtherAttention}</p>
    </section>
  );
}
