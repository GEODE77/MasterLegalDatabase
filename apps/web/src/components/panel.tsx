import type { ReactNode } from "react";

type PanelProps = {
  title: string;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
};

export function Panel({ title, icon, action, children }: PanelProps) {
  return (
    <section className="panel">
      <header className="panel-header">
        <div className="panel-title">
          {icon}
          <span>{title}</span>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function PanelBody({ children }: { children: ReactNode }) {
  return <div className="panel-body">{children}</div>;
}
