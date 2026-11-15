# Analisi Riferimenti Visivi

> Fonti: screenshot acquisiti il 2026-11-15 da Dribbble e salvati in `.design-refs/operator/` e `.design-refs/recipient/`.
> Gli screenshot sono esclusivamente riferimento comparativo: nessun asset protetto è incorporato nel codice.

## Operatore

### Palette
- Sfondo base: #1A1B1E (Velize, tela esterna) / #0C110E (City Pilot, tela verde-nera)
- Pannello: #1C1D21
- Pannello alternativo: #202226
- Bordo: #2E3138
- Testo primario: #F4F5F7
- Testo secondario: #9AA0A8
- Accento: #A78BFA (marker viola Velize) e #C6F24E / #6EE7B7 (verde neon City Pilot)
- Severity: low #34D399, medium #F5B93B, high #F97316, critical #EF5A5A

### Tipografia
- Famiglia: sans-serif geometrica (Velize: Inter-like; City Pilot: Manrope-like)
- Pesi usati: 400, 500, 600, 700
- Dimensione base: 12-14px
- Dimensione titoli: 18-20px (titoli pannello); numeri KPI 26-40px

### Layout
- Colonne: workspace a griglia con pannello mappa protagonista (60-65%) + colonna alert (35-40%)
- Densità: alta
- Radius card: 10-14px
- Ombre: assenti o appena percettibili; separazione affidata a bordi 1px

### Pattern ricorrenti
- Pannelli scuri con bordo sottile e header con titolo a sinistra, azioni a destra ("View All", filtri).
- Tabella alert con colonne Time / Alerts / Location / Description e righe compatte.
- Marker mappa circolari colorati per categoria, con badge compatto e popover in hover.
- Gauge radiali con valore centrale grande, etichetta inferiore e stato testuale ("Good", "Normal").
- Micro-etichette uppercase con tracking ampio per i metadati; badge di stato pill.

## Recipient

### Palette
- Sfondo base: #F5F6F8
- Card: #FFFFFF
- Bordo: #E7E9EC
- Testo primario: #14181C
- Testo secondario: #78818C
- Accento cittadino: #0284C7 (blu civico rassicurante)
- Accento turista: #EA580C (corallo caldo)

### Tipografia
- Famiglia: sans-serif arrotondata (Inter/Poppins-like)
- Pesi usati: 400, 500, 600, 700
- Dimensione base: 14-15px
- Dimensione titoli: 20-24px

### Layout
- Densità: bassa / ariosa
- Radius card: 16-24px (pill per filtri e azioni: 9999px)
- Ombre: leggere e morbide, diffuse (0 8px 24px rgba(15,23,42,0.06))
- Spaziature: generose, 20-32px tra sezioni

### Pattern ricorrenti
- Search bar grande in alto con bordo chiaro e icona a sinistra.
- Card orizzontali con blocco visivo a sinistra e testo a destra, raggi ampi e padding interno 16-20px.
- Chat con bolle arrotondate: utente a destra su fondo scuro/accento, assistente su card chiara con azioni pill.
- Chip di risposta rapida con bordo sottile e testo breve, sempre leggibili e non allarmistici.
- CTA primaria a pillola, piena, con ampia area di tocco su mobile.
