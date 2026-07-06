"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactElement, type ReactNode } from "react";

import { usePersonalization } from "@/hooks/usePersonalization";

type RouteMotionProviderProps = {
  children: ReactNode;
};

export function RouteMotionProvider({ children }: RouteMotionProviderProps): ReactElement {
  const pathname = usePathname();
  const router = useRouter();
  const { logEvent } = usePersonalization();

  useEffect(() => {
    const startedAt = Date.now();
    let maxScrollDepth = 0;

    logEvent("route_view", { pathname });

    function updateScrollDepth(): void {
      const scrollable = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      maxScrollDepth = Math.max(maxScrollDepth, Math.min(1, window.scrollY / scrollable));
    }

    window.addEventListener("scroll", updateScrollDepth, { passive: true });
    updateScrollDepth();

    return () => {
      updateScrollDepth();
      logEvent("page_engagement", {
        pathname,
        scrollDepth: Number(maxScrollDepth.toFixed(2)),
        secondsOnPage: Math.round((Date.now() - startedAt) / 1000),
      });
      window.removeEventListener("scroll", updateScrollDepth);
    };
  }, [logEvent, pathname]);

  useEffect(() => {
    function navigateWithTransition(event: MouseEvent): void {
      if (
        event.defaultPrevented
        || event.button !== 0
        || event.altKey
        || event.ctrlKey
        || event.metaKey
        || event.shiftKey
      ) {
        return;
      }

      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      const anchor = target.closest("a[href]");

      if (!(anchor instanceof HTMLAnchorElement)) {
        return;
      }

      const href = anchor.getAttribute("href");

      if (
        !href
        || anchor.target
        || anchor.hasAttribute("download")
        || href.startsWith("mailto:")
        || href.startsWith("tel:")
      ) {
        return;
      }

      const destination = new URL(href, window.location.href);

      if (destination.origin !== window.location.origin) {
        return;
      }

      const nextPath = `${destination.pathname}${destination.search}${destination.hash}`;
      const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;

      if (nextPath === currentPath) {
        return;
      }

      event.preventDefault();
      startRouteTransition(() => router.push(nextPath));
    }

    document.addEventListener("click", navigateWithTransition);
    return () => document.removeEventListener("click", navigateWithTransition);
  }, [router]);

  return <div className="route-motion-shell">{children}</div>;
}

function startRouteTransition(action: () => void): void {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const viewTransition = (document as Document & {
    startViewTransition?: (callback: () => void) => void;
  }).startViewTransition;

  if (reduceMotion) {
    action();
    return;
  }

  if (viewTransition) {
    viewTransition.call(document, action);
    return;
  }

  document.documentElement.classList.add("is-route-transitioning");
  window.setTimeout(() => {
    action();
    window.setTimeout(() => {
      document.documentElement.classList.remove("is-route-transitioning");
    }, 240);
  }, 120);
}
