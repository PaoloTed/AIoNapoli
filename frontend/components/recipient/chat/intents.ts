/**
 * @purpose Intent statici della chat recipient
 * @contracts nessuno
 * @tokens recipient
 * @verified 2026-11-15
 */

export const intents: Record<string, string> = {
  come_arrivo: "come arrivo",
  cosa_evito: "cosa evito",
  percorso_alternativo: "percorso alternativo",
  cosa_visitare: "cosa posso visitare",
  dove_non_c_e_folla: "dove non c'è folla",
  cosa_c_e_vicino: "cosa c'è vicino",
};

export const citizenQuickActions = ["Come arrivo in ufficio?", "Cosa evito oggi?", "Percorso alternativo"] as const;

export const touristQuickActions = ["Cosa posso visitare?", "Dove non c'è folla?", "Cosa c'è nelle vicinanze?"] as const;
