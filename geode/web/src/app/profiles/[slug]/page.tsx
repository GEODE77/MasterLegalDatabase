import type { ReactElement } from "react";

type ProfilePageProps = {
  params: Promise<{ slug: string }>;
};

export default async function ProfilePage({ params }: ProfilePageProps): Promise<ReactElement> {
  const { slug } = await params;
  const name = nameFromSlug(slug);

  return (
    <main className="profile-page">
      <section className="profile-document" aria-label="Profile">
        <p className="profile-kicker">Public profile</p>
        <h1>{name}</h1>
        <p>{name} contributes regulatory judgment to public forum discussions.</p>
        <div className="profile-activity">
          <span>Recent activity</span>
          <p>{name} has contributed to forum interpretation and regulatory review.</p>
        </div>
      </section>
    </main>
  );
}

function nameFromSlug(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || "Geode Member";
}
