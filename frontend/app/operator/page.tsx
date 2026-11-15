/**
 * @purpose Redirect deterministico della radice operatore verso la scheda Situazione
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import { redirect } from "next/navigation";

export default function OperatorPage() {
  redirect("/operator/situation");
}
