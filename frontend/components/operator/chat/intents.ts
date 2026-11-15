/**
 * @purpose Mappatura statica tra quick action e chiavi di retrieval
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

export const operatorQuickActions = [
  "Perché questo piano?",
  "Cosa è stato scartato?",
  "Quali finding sono critici?",
] as const;

export const operatorIntentQueries: Record<(typeof operatorQuickActions)[number], string> = {
  "Perché questo piano?": "piano motivazione priorità regola",
  "Cosa è stato scartato?": "route_invalidated scartato linea 2 cantiere",
  "Quali finding sono critici?": "densità critica bagnoli crowding",
};
