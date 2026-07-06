import type {
  PersonalizationBehaviorEvent,
  PersonalizationEventInput,
  PersonalizationPreferenceUpdate,
  PersonalizationSnapshot,
} from "./types";

const SNAPSHOT_PREFIX = "geode.personalization.snapshot.v1:";
const QUEUE_DB = "geode-personalization";
const QUEUE_STORE = "actions";
const QUEUE_VERSION = 1;

export type PersonalizationQueueAction =
  | {
      actionId: string;
      createdAt: string;
      kind: "delete";
      userId: string;
    }
  | {
      actionId: string;
      createdAt: string;
      kind: "event";
      userId: string;
      payload: { events: PersonalizationEventInput[] };
    }
  | {
      actionId: string;
      createdAt: string;
      kind: "preferences";
      userId: string;
      payload: PersonalizationPreferenceUpdate;
    };

export function loadCachedSnapshot(userId: string): PersonalizationSnapshot | null {
  const storage = safeLocalStorage();

  if (!storage) {
    return null;
  }

  const raw = storage.getItem(snapshotKey(userId));

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as PersonalizationSnapshot;
  } catch {
    return null;
  }
}

export function saveCachedSnapshot(snapshot: PersonalizationSnapshot): void {
  const storage = safeLocalStorage();

  if (!storage) {
    return;
  }

  storage.setItem(snapshotKey(snapshot.userId), JSON.stringify(snapshot));
}

export function clearCachedSnapshot(userId: string): void {
  const storage = safeLocalStorage();

  if (!storage) {
    return;
  }

  storage.removeItem(snapshotKey(userId));
}

export async function enqueueAction(action: PersonalizationQueueAction): Promise<void> {
  const db = await openQueueDb();

  if (!db) {
    return;
  }

  await withTransaction(db, "readwrite", (store) => {
    store.put(action);
  });
}

export async function readQueuedActions(userId: string): Promise<PersonalizationQueueAction[]> {
  const db = await openQueueDb();

  if (!db) {
    return [];
  }

  const actions = await withRequest<PersonalizationQueueAction[]>(db, (store) => store.getAll());
  return actions.filter((action) => action.userId === userId).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export async function removeQueuedAction(actionId: string): Promise<void> {
  const db = await openQueueDb();

  if (!db) {
    return;
  }

  await withTransaction(db, "readwrite", (store) => {
    store.delete(actionId);
  });
}

export async function clearQueuedActions(userId: string): Promise<void> {
  const actions = await readQueuedActions(userId);
  await Promise.all(actions.map((action) => removeQueuedAction(action.actionId)));
}

export function createEventAction(
  userId: string,
  events: PersonalizationEventInput[],
): PersonalizationQueueAction {
  return {
    actionId: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    kind: "event",
    payload: { events },
    userId,
  };
}

export function createPreferenceAction(
  userId: string,
  payload: PersonalizationPreferenceUpdate,
): PersonalizationQueueAction {
  return {
    actionId: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    kind: "preferences",
    payload,
    userId,
  };
}

export function createDeleteAction(userId: string): PersonalizationQueueAction {
  return {
    actionId: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    kind: "delete",
    userId,
  };
}

export function toBehaviorEvent(
  event: PersonalizationEventInput,
): PersonalizationBehaviorEvent {
  return {
    eventId: crypto.randomUUID(),
    payload: event.payload ?? {},
    recordedAt: new Date().toISOString(),
    source: "behavior",
    type: event.type,
  };
}

function snapshotKey(userId: string): string {
  return `${SNAPSHOT_PREFIX}${userId}`;
}

function safeLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

async function openQueueDb(): Promise<IDBDatabase | null> {
  if (typeof window === "undefined" || !("indexedDB" in window)) {
    return null;
  }

  return new Promise((resolve) => {
    const request = window.indexedDB.open(QUEUE_DB, QUEUE_VERSION);

    request.onupgradeneeded = () => {
      request.result.createObjectStore(QUEUE_STORE, { keyPath: "actionId" });
    };

    request.onerror = () => resolve(null);
    request.onsuccess = () => resolve(request.result);
  });
}

async function withTransaction(
  db: IDBDatabase,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, mode);
    const store = transaction.objectStore(QUEUE_STORE);
    try {
      run(store);
    } catch (error) {
      reject(error);
      return;
    }

    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

async function withRequest<T>(
  db: IDBDatabase,
  run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, "readonly");
    const store = transaction.objectStore(QUEUE_STORE);
    const request = run(store);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    transaction.onerror = () => reject(transaction.error);
  });
}
