"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import {
  clearCachedSnapshot,
  clearQueuedActions,
  createDeleteAction,
  createEventAction,
  createPreferenceAction,
  enqueueAction,
  loadCachedSnapshot,
  readQueuedActions,
  removeQueuedAction,
  saveCachedSnapshot,
  toBehaviorEvent,
  type PersonalizationQueueAction,
} from "@/lib/personalization/client";
import { derivePersonalizationProfile } from "@/lib/personalization/shared";
import type {
  JsonObject,
  PersonalizationEventInput,
  PersonalizationPreferenceUpdate,
  PersonalizationSnapshot,
} from "@/lib/personalization/types";

type PersonalizationContextValue = {
  deletePersonalization: () => Promise<void>;
  logEvent: (type: string, payload?: JsonObject) => void;
  profile: PersonalizationSnapshot;
  ready: boolean;
  setPreferences: (update: PersonalizationPreferenceUpdate) => Promise<void>;
  userId: string;
};

export const PersonalizationContext = createContext<PersonalizationContextValue | null>(null);

const EVENT_FLUSH_INTERVAL_MS = 12_000;
const EVENT_FLUSH_THRESHOLD = 8;

type PersonalizationProviderProps = {
  children: ReactNode;
  initialSnapshot: PersonalizationSnapshot;
};

export function PersonalizationProvider({
  children,
  initialSnapshot,
}: PersonalizationProviderProps): ReactElement {
  const [profile, setProfile] = useState(() => selectInitialSnapshot(initialSnapshot));
  const [ready, setReady] = useState(false);
  const flushInFlight = useRef(false);
  const flushTimer = useRef<number | null>(null);
  const pendingEventCount = useRef(0);
  const profileRef = useRef(profile);

  useEffect(() => {
    return () => {
      if (flushTimer.current !== null) {
        window.clearTimeout(flushTimer.current);
      }
    };
  }, []);

  useEffect(() => {
    profileRef.current = profile;
    saveCachedSnapshot(profile);
  }, [profile]);

  const flushQueue = useCallback(async (): Promise<void> => {
    if (flushInFlight.current) {
      return;
    }

    flushInFlight.current = true;

    try {
      if (flushTimer.current !== null) {
        window.clearTimeout(flushTimer.current);
        flushTimer.current = null;
      }

      const actions = await readQueuedActions(profileRef.current.userId);

      if (actions.length === 0) {
        pendingEventCount.current = 0;
        return;
      }

      const eventActions = actions.filter((action) => action.kind === "event") as Array<Extract<
        PersonalizationQueueAction,
        { kind: "event" }
      >>;

      if (eventActions.length > 0) {
        const response = await fetch("/api/personalization", {
          body: JSON.stringify({
            events: eventActions.flatMap((action) => action.payload.events),
          }),
          headers: { "Content-Type": "application/json" },
          method: "POST",
        });

        if (response.ok) {
          const data = (await response.json()) as { snapshot: PersonalizationSnapshot };
          setProfile(data.snapshot);
          await Promise.all(eventActions.map((action) => removeQueuedAction(action.actionId)));
          pendingEventCount.current = 0;
        } else {
          return;
        }
      }

      const remainingActions = await readQueuedActions(profileRef.current.userId);
      for (const action of remainingActions) {
        if (action.kind === "delete") {
          const response = await fetch("/api/personalization", { method: "DELETE" });
          if (response.ok) {
            const data = (await response.json()) as { snapshot: PersonalizationSnapshot };
            clearCachedSnapshot(data.snapshot.userId);
            await clearQueuedActions(data.snapshot.userId);
            setProfile(createBlankSnapshot(data.snapshot.userId));
            return;
          }

          return;
        }

        if (action.kind === "preferences") {
          const response = await fetch("/api/personalization", {
            body: JSON.stringify(action.payload),
            headers: { "Content-Type": "application/json" },
            method: "PUT",
          });

          if (!response.ok) {
            return;
          }

          const data = (await response.json()) as { snapshot: PersonalizationSnapshot };
          setProfile(data.snapshot);
          await removeQueuedAction(action.actionId);
        }
      }
    } finally {
      flushInFlight.current = false;
    }
  }, []);

  const scheduleEventFlush = useCallback((): void => {
    if (pendingEventCount.current >= EVENT_FLUSH_THRESHOLD) {
      void flushQueue();
      return;
    }

    if (flushTimer.current !== null) {
      return;
    }

    flushTimer.current = window.setTimeout(() => {
      flushTimer.current = null;
      void flushQueue();
    }, EVENT_FLUSH_INTERVAL_MS);
  }, [flushQueue]);

  const syncFromServer = useCallback(async (): Promise<void> => {
    const response = await fetch("/api/personalization", { cache: "no-store" });

    if (!response.ok) {
      return;
    }

    const data = (await response.json()) as { snapshot: PersonalizationSnapshot };
    if (isNewer(data.snapshot, profileRef.current)) {
      setProfile(data.snapshot);
    }
  }, []);

  useEffect(() => {
    setReady(true);
    void hydrate();

    function handleStorage(event: StorageEvent): void {
      if (event.key === snapshotKey(profileRef.current.userId) && event.newValue) {
        try {
          const next = JSON.parse(event.newValue) as PersonalizationSnapshot;
          if (isNewer(next, profileRef.current)) {
            setProfile(next);
          }
        } catch {
          // Ignore malformed cache entries.
        }
      }
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener("online", handleOnline);
    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };

    async function hydrate(): Promise<void> {
      const cached = loadCachedSnapshot(initialSnapshot.userId);
      if (cached && isNewer(cached, profileRef.current)) {
        setProfile(cached);
      }

      await syncFromServer();
      void flushQueue();
    }

    function handleOnline(): void {
      void flushQueue();
    }

    function handleVisibilityChange(): void {
      if (document.visibilityState === "visible") {
        void flushQueue();
      } else {
        void flushQueue();
      }
    }
  }, [flushQueue, initialSnapshot, initialSnapshot.userId, syncFromServer]);

  const logEvent = useCallback((type: string, payload: JsonObject = {}): void => {
    const next = applyBehaviorEvent(profileRef.current, {
      payload,
      type,
    });
    setProfile(next);
    pendingEventCount.current += 1;
    void enqueueAction(createEventAction(next.userId, [{ payload, type }])).then(scheduleEventFlush);
  }, [scheduleEventFlush]);

  const setPreferences = useCallback(async (update: PersonalizationPreferenceUpdate): Promise<void> => {
    const next = applyPreferenceUpdate(profileRef.current, update);
    setProfile(next);
    await enqueueAction(createPreferenceAction(next.userId, update));
    void flushQueue();
  }, [flushQueue]);

  const deletePersonalization = useCallback(async (): Promise<void> => {
    const current = profileRef.current;
    const action: PersonalizationQueueAction = createDeleteAction(current.userId);
    await enqueueAction(action);
    clearCachedSnapshot(current.userId);
    setProfile(createBlankSnapshot(current.userId));
    void flushQueue();
  }, [flushQueue]);

  return (
    <PersonalizationContext.Provider
      value={{
        deletePersonalization,
        logEvent,
        profile,
        ready,
        setPreferences,
        userId: profile.userId,
      }}
    >
      {children}
    </PersonalizationContext.Provider>
  );
}

function selectInitialSnapshot(initialSnapshot: PersonalizationSnapshot): PersonalizationSnapshot {
  const cached = loadCachedSnapshot(initialSnapshot.userId);

  if (cached && isNewer(cached, initialSnapshot)) {
    return cached;
  }

  return initialSnapshot;
}

function applyPreferenceUpdate(
  current: PersonalizationSnapshot,
  update: PersonalizationPreferenceUpdate,
): PersonalizationSnapshot {
  const now = new Date().toISOString();
  const byKey = new Map(current.explicitAnswers.map((answer) => [answer.key, answer]));

  for (const answer of update.answers) {
    byKey.set(answer.key, {
      answeredAt: now,
      key: answer.key,
      sensitivity: answer.sensitivity ?? "public",
      source: "explicit",
      value: answer.value,
    });
  }

  const next = {
    ...current,
    explicitAnswers: Array.from(byKey.values()),
    updatedAt: now,
  };

  return {
    ...next,
    derived: derivePersonalizationProfile(next),
  };
}

function applyBehaviorEvent(
  current: PersonalizationSnapshot,
  event: PersonalizationEventInput,
): PersonalizationSnapshot {
  const now = new Date().toISOString();
  const next = {
    ...current,
    behaviorEvents: [
      ...current.behaviorEvents,
      toBehaviorEvent(event),
    ].slice(-250),
    updatedAt: now,
  };

  return {
    ...next,
    derived: derivePersonalizationProfile(next),
  };
}

function createBlankSnapshot(userId: string): PersonalizationSnapshot {
  const now = new Date().toISOString();
  const empty = {
    behaviorEvents: [],
    explicitAnswers: [
      {
        answeredAt: now,
        key: "displayName",
        sensitivity: "public" as const,
        source: "explicit" as const,
        value: "JP",
      },
    ],
    schemaVersion: 1 as const,
    updatedAt: now,
    userId,
  };

  return {
    ...empty,
    derived: derivePersonalizationProfile(empty),
  };
}

function snapshotKey(userId: string): string {
  return `geode.personalization.snapshot.v1:${userId}`;
}

function isNewer(left: PersonalizationSnapshot, right: PersonalizationSnapshot): boolean {
  return Date.parse(left.updatedAt) > Date.parse(right.updatedAt);
}
