/**
 * @purpose Fallback trasparente su dataset mock quando il backend non risponde
 * @contracts ApiError
 * @tokens shared
 * @verified 2026-11-15
 */

import { ApiError } from "./client";

export function isMockMode(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCKS === "true";
}

export async function withMockFallback<T>(
  live: () => Promise<T>,
  mock: () => T | Promise<T>,
  opts?: { timeoutMs?: number },
): Promise<{ data: T; isSimulated: boolean }> {
  if (isMockMode()) {
    const data = await mock();
    return { data, isSimulated: true };
  }

  try {
    void opts;
    const data = await live();
    return { data, isSimulated: false };
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.kind === "timeout" || error.kind === "network")) {
      const data = await mock();
      return { data, isSimulated: true };
    }
    throw error;
  }
}
