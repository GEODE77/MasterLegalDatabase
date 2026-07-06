import type { ReactElement } from "react";

export function OnboardingBackground(): ReactElement {
  return (
    <div aria-hidden="true" className="onboarding-background">
      <div className="onboarding-threads onboarding-threads-a" />
      <div className="onboarding-threads onboarding-threads-b" />
      <div className="onboarding-scan-field" />
      <div className="onboarding-vignette" />
    </div>
  );
}
