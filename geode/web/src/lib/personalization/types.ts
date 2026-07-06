export type JsonPrimitive = string | number | boolean | null;

export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];

export type JsonObject = { [key: string]: JsonValue };

export type PersonalizationSensitivity = "public" | "private";

export type PersonalizationExplicitAnswer = {
  answeredAt: string;
  key: string;
  sensitivity: PersonalizationSensitivity;
  source: "explicit";
  value: JsonValue;
};

export type PersonalizationBehaviorEvent = {
  eventId: string;
  payload: JsonObject;
  recordedAt: string;
  source: "behavior";
  type: string;
};

export type PersonalizationDerivedProfile = {
  agencyVector: Array<{ key: string; weight: number }>;
  behaviorScore: number;
  confidence: number;
  displayName: string;
  industryVector: Array<{ key: string; weight: number }>;
  lastActiveAt: string | null;
  modelVersion: 2;
  primaryInterest: string | null;
  preferredTone: "direct" | "collaborative" | "analytical";
  readingDensity: "light" | "focused" | "deep";
  recomputedAt: string;
  roleVector: Array<{ key: string; weight: number }>;
  surfaceVector: Array<{ key: string; weight: number }>;
  topicSignals: Array<{ key: string; weight: number }>;
  initials: string;
};

export type PersonalizationSnapshot = {
  behaviorEvents: PersonalizationBehaviorEvent[];
  derived: PersonalizationDerivedProfile;
  explicitAnswers: PersonalizationExplicitAnswer[];
  schemaVersion: 1;
  updatedAt: string;
  userId: string;
};

export type PersonalizationPreferenceUpdate = {
  answers: Array<{
    key: string;
    sensitivity?: PersonalizationSensitivity;
    value: JsonValue;
  }>;
};

export type PersonalizationEventInput = {
  payload?: JsonObject;
  type: string;
};

export type PersonalizationDeleteResponse = {
  deleted: true;
  snapshot: PersonalizationSnapshot;
};
