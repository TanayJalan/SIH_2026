import type { QueryClient } from "@tanstack/react-query";

import { getApplication } from "./api";

/** Shared TanStack Query key so prefetching and the page read the same cache entry. */
export const applicationQueryKey = (applicationId: string) =>
  ["application", applicationId] as const;

const ACCESS_TOKEN_KEY = "aicte.access_token";

/* `/applications/new` is the wizard, not a case file. */
const CASE_FILE_PATH =
  /^\/applications\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\/edit)?\/?$/i;

/**
 * Start the case-file request while the route chunk is still downloading.
 *
 * The chunk and the API call would otherwise be sequential: the page module is
 * needed before it can call the API. Both the token and the application id are
 * available from browser storage and the URL, so the request can begin with the
 * entry bundle instead.
 */
export function prefetchRouteData(queryClient: QueryClient): void {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token) {
    return;
  }
  const match = window.location.pathname.match(CASE_FILE_PATH);
  if (!match) {
    return;
  }
  const applicationId = decodeURIComponent(match[1]);
  void queryClient.prefetchQuery({
    queryKey: applicationQueryKey(applicationId),
    queryFn: () => getApplication(token, applicationId),
    staleTime: 30_000,
    retry: false,
  });
}
