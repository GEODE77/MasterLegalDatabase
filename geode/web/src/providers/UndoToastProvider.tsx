"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

type UndoToastInput = {
  actionLabel?: string;
  durationMs?: number;
  message: string;
  onExpire?: () => Promise<void> | void;
  onUndo?: () => Promise<void> | void;
};

type UndoToast = Required<Pick<UndoToastInput, "message">> & {
  actionLabel?: string;
  id: string;
  isLeaving: boolean;
  onExpire?: () => Promise<void> | void;
  onUndo?: () => Promise<void> | void;
};

type UndoToastContextValue = {
  showToast: (toast: UndoToastInput) => void;
  showUndoToast: (toast: UndoToastInput) => void;
};

const STATUS_TOAST_DURATION_MS = 4_000;
const UNDO_TOAST_DURATION_MS = 10_000;
const TOAST_EXIT_MS = 180;
const SUCCESS_GLOW_MS = 700;

const UndoToastContext = createContext<UndoToastContextValue | null>(null);

type UndoToastProviderProps = {
  children: ReactNode;
};

export function UndoToastProvider({ children }: UndoToastProviderProps): ReactElement {
  const [toasts, setToasts] = useState<UndoToast[]>([]);
  const timers = useRef(new Map<string, number>());

  useEffect(() => {
    const activeTimers = timers.current;

    return () => {
      for (const timer of activeTimers.values()) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  const removeToast = useCallback((id: string, runExpire: boolean): void => {
    const timer = timers.current.get(id);

    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }

    let expiringToast: UndoToast | undefined;
    setToasts((current) =>
      current.map((toast) => {
        if (toast.id !== id) {
          return toast;
        }

        expiringToast = toast;
        return { ...toast, isLeaving: true };
      }),
    );

    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));

      if (runExpire) {
        void expiringToast?.onExpire?.();
      }
    }, TOAST_EXIT_MS);
  }, []);

  const showToast = useCallback((input: UndoToastInput): void => {
    const id = `toast-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    const activeElement = document.activeElement;

    if (activeElement instanceof HTMLElement && isInteractiveElement(activeElement)) {
      activeElement.classList.add("interaction-success");
      window.setTimeout(() => activeElement.classList.remove("interaction-success"), SUCCESS_GLOW_MS);
    }

    const toast: UndoToast = {
      actionLabel: input.actionLabel,
      id,
      isLeaving: false,
      message: input.message,
      onExpire: input.onExpire,
      onUndo: input.onUndo,
    };

    setToasts((current) => [...current, toast].slice(-3));

    const timer = window.setTimeout(() => {
      removeToast(id, true);
    }, input.durationMs ?? STATUS_TOAST_DURATION_MS);

    timers.current.set(id, timer);
  }, [removeToast]);

  const showUndoToast = useCallback(
    (input: UndoToastInput): void => {
      showToast({
        ...input,
        actionLabel: input.actionLabel ?? "Undo",
        durationMs: input.durationMs ?? UNDO_TOAST_DURATION_MS,
      });
    },
    [showToast],
  );

  async function undo(toast: UndoToast): Promise<void> {
    removeToast(toast.id, false);
    await toast.onUndo?.();
  }

  return (
    <UndoToastContext.Provider value={{ showToast, showUndoToast }}>
      {children}
      <div className="undo-toast-region" aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <div className={`undo-toast${toast.isLeaving ? " is-leaving" : ""}`} key={toast.id} role="status">
            <span>{toast.message}</span>
            {toast.actionLabel ? (
              <button onClick={() => void undo(toast)} type="button">
                {toast.actionLabel}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </UndoToastContext.Provider>
  );
}

function isInteractiveElement(element: HTMLElement): boolean {
  return Boolean(element.closest("button, a[href], input, textarea, select, [role='button'], summary"));
}

export function useUndoToast(): UndoToastContextValue {
  const context = useContext(UndoToastContext);

  if (!context) {
    throw new Error("useUndoToast must be used within UndoToastProvider");
  }

  return context;
}
