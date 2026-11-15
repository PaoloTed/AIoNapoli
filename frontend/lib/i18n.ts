import type { AgentName, PlanTarget } from "./contracts";
import type { Locale } from "./format";

export type { Locale };

export type Dictionary = {
  appName: string;
  nav: {
    home: string;
    operator: string;
    tourist: string;
    citizen: string;
    verify: string;
  };
  shell: {
    scenarioLabel: string;
    timeLabel: string;
    contractLabel: string;
    contractMismatch: string;
    status: {
      live: string;
      degraded: string;
      offline: string;
    };
    languageLabel: string;
  };
  home: {
    heading: string;
    subheading: string;
    scenarioActive: string;
    cards: {
      operator: { title: string; description: string; cta: string };
      tourist: { title: string; description: string; cta: string };
      citizen: { title: string; description: string; cta: string };
    };
  };
  provenance: {
    real: string;
    simulated: string;
    unavailable: string;
    templateText: string;
  };
  agents: Record<AgentName, string>;
  targets: Record<PlanTarget, string>;
  operator: {
    title: string;
    findingsTitle: string;
    timelineTitle: string;
    mapTitle: string;
    decisionTitle: string;
    planTitle: string;
    relevanceTitle: string;
    reasoningTitle: string;
    metricsTitle: string;
    repeatButton: string;
    repeatLoading: string;
    repeatSame: string;
    repeatDifferent: string;
    streamUnavailable: string;
    streamRetry: string;
    streamEmpty: string;
    noRulesBanner: string;
    conflictDetected: string;
    noConflict: string;
    ruleFired: string;
    ruleNotFired: string;
    confidence: string;
    source: string;
    reference: string;
    density: string;
    congestion: string;
    zone: string;
    heavyRain: string;
    yes: string;
    no: string;
    attendance: string;
    missingCardNote: string;
    metricSteps: string;
    metricTargets: string;
    metricActions: string;
    metricSimulated: string;
    metricLatency: string;
  };
  tourist: {
    title: string;
    subtitle: string;
    primaryRecommendation: string;
    alternativesTitle: string;
    estimatedTime: string;
    moreActions: (count: number) => string;
    simulatedNotice: string;
    noActions: string;
  };
  citizen: {
    title: string;
    subtitle: string;
    primaryRecommendation: string;
    publicServiceTitle: string;
    zoneStateTitle: string;
    zoneVeryCrowded: string;
    zoneElevated: string;
    zoneNormal: string;
    moreServicesTitle: string;
    simulatedNotice: string;
    noActions: string;
  };
  map: {
    notConfiguredTitle: string;
    notConfiguredDetail: string;
    vehiclesTitle: string;
    noVehicles: string;
    zonesTitle: string;
    noHighlightedZone: string;
    routeLabel: string;
    ageLabel: string;
    lastObserved: string;
  };
  states: {
    retry: string;
    knownScenarios: string;
    requestedScenario: string;
    notFoundTitle: string;
    degradedStream: string;
    degradedBackend: string;
    degradedUpstream: string;
    contractMismatchTitle: string;
    contractMismatchDetail: string;
    invalidFinding: string;
    agentMismatch: string;
    missingFinding: string;
    agentRefusal: string;
    configInvalid: string;
    internalError: string;
  };
};

export const DICTIONARY: Record<Locale, Dictionary> = {
  it: {
    appName: "Napoli Agentic City",
    nav: {
      home: "Punti di vista",
      operator: "Operatore",
      tourist: "Turista",
      citizen: "Cittadino",
      verify: "Verifica",
    },
    shell: {
      scenarioLabel: "Scenario",
      timeLabel: "Ora (Europe/Rome)",
      contractLabel: "Contratto",
      contractMismatch: "Versione contratto non allineata",
      status: {
        live: "live",
        degraded: "degraded",
        offline: "offline",
      },
      languageLabel: "Lingua",
    },
    home: {
      heading: "Scegli il punto di vista sullo scenario",
      subheading: "Stessi dati verificati, tre viste dedicate senza sovrapposizioni tra ruoli.",
      scenarioActive: "Scenario configurato",
      cards: {
        operator: {
          title: "Operatore",
          description:
            "Sala operativa: finding con provenienza, mappa mezzi, timeline SSE delle regole, conflitti, rilevanza e reasoning log.",
          cta: "Apri sala operativa",
        },
        tourist: {
          title: "Turista",
          description:
            "Vista bilingue (IT/EN): indicazione principale, alternative ordinate per rilevanza e mappa compatta della zona.",
          cta: "Apri vista turista",
        },
        citizen: {
          title: "Cittadino",
          description:
            "Servizio pubblico consigliato, stato qualitativo della zona senza metriche interne e mappa di prossimità.",
          cta: "Apri vista cittadino",
        },
      },
    },
    provenance: {
      real: "Reale",
      simulated: "SIMULATO",
      unavailable: "NON DISPONIBILE",
      templateText: "testo da template",
    },
    agents: {
      mobility: "Mobilità",
      crowding: "Affollamento",
      context: "Contesto",
    },
    targets: {
      operator: "Operatore",
      tourist: "Turista",
      citizen: "Cittadino",
    },
    operator: {
      title: "Sala operativa",
      findingsTitle: "Finding dagli agenti",
      timelineTitle: "Timeline delle regole (SSE)",
      mapTitle: "Mappa mezzi e zone",
      decisionTitle: "Decisione",
      planTitle: "Piano per destinatario",
      relevanceTitle: "Rilevanza e contributi",
      reasoningTitle: "Reasoning log",
      metricsTitle: "Metriche osservabili",
      repeatButton: "Ripeti decisione",
      repeatLoading: "Verifica in corso...",
      repeatSame: "same",
      repeatDifferent: "diverso",
      streamUnavailable: "Stream non disponibile",
      streamRetry: "Riprova stream",
      streamEmpty: "In attesa degli eventi della trace...",
      noRulesBanner: "Nessuna regola scattata: piano di monitoraggio attivo senza conflitti.",
      conflictDetected: "Conflitto rilevato",
      noConflict: "Nessun conflitto",
      ruleFired: "Scattata",
      ruleNotFired: "Non scattata",
      confidence: "Confidenza",
      source: "Fonte",
      reference: "Riferimento",
      density: "Densità",
      congestion: "Congestione",
      zone: "Zona",
      heavyRain: "Pioggia intensa",
      yes: "Sì",
      no: "No",
      attendance: "Affluenza attesa",
      missingCardNote: "Dato non disponibile per questo agente",
      metricSteps: "Passi reasoning log",
      metricTargets: "Copertura target",
      metricActions: "Azioni nel piano",
      metricSimulated: "Finding simulati",
      metricLatency: "Delta finding → decisione",
    },
    tourist: {
      title: "Guida turista",
      subtitle: "Indicazioni essenziali su come arrivare e cosa fare adesso",
      primaryRecommendation: "Indicazione principale",
      alternativesTitle: "Alternative consigliate",
      estimatedTime: "Tempo stimato",
      moreActions: (count: number) => `Altre ${count} azioni`,
      simulatedNotice: "Informazione basata su almeno un dato simulato",
      noActions: "Nessuna azione disponibile per il turista in questo scenario.",
    },
    citizen: {
      title: "Guida cittadino",
      subtitle: "Quale servizio pubblico prendere e condizioni della zona",
      primaryRecommendation: "Indicazione principale",
      publicServiceTitle: "Servizio pubblico",
      zoneStateTitle: "Stato della zona",
      zoneVeryCrowded: "Zona molto affollata",
      zoneElevated: "Zona con affluenza elevata",
      zoneNormal: "Zona con affluenza regolare",
      moreServicesTitle: "Altre opzioni di servizio",
      simulatedNotice: "Informazione basata su almeno un dato simulato",
      noActions: "Nessun servizio disponibile per il cittadino in questo scenario.",
    },
    map: {
      notConfiguredTitle: "Mappa non configurata",
      notConfiguredDetail:
        "Imposta NEXT_PUBLIC_MAPBOX_TOKEN per abilitare la vista cartografica Mapbox. I dati di mezzi e zone restano leggibili qui sotto.",
      vehiclesTitle: "Posizioni dei mezzi",
      noVehicles: "Nessuna posizione veicolo disponibile.",
      zonesTitle: "Zone evidenziate (geo-fence)",
      noHighlightedZone: "Nessuna zona evidenziata dai finding.",
      routeLabel: "Linea",
      ageLabel: "Età dato",
      lastObserved: "Ultimo rilevamento",
    },
    states: {
      retry: "Riprova",
      knownScenarios: "Scenari configurati",
      requestedScenario: "Scenario richiesto",
      notFoundTitle: "Scenario non trovato",
      degradedStream: "Stream SSE non disponibile: la decisione resta valida.",
      degradedBackend: "Backend non raggiungibile",
      degradedUpstream: "Sorgente esterna non raggiungibile",
      contractMismatchTitle: "Versione del contratto inattesa",
      contractMismatchDetail:
        "I campi sconosciuti restano in sola lettura e non vengono interpretati.",
      invalidFinding: "Dato non conforme",
      agentMismatch: "Il dato non appartiene a questo agente",
      missingFinding: "Nessun finding disponibile",
      agentRefusal: "Dato non disponibile",
      configInvalid: "Configurazione del backend non valida",
      internalError: "Errore interno del servizio",
    },
  },
  en: {
    appName: "Napoli Agentic City",
    nav: {
      home: "Views",
      operator: "Operator",
      tourist: "Tourist",
      citizen: "Citizen",
      verify: "Verify",
    },
    shell: {
      scenarioLabel: "Scenario",
      timeLabel: "Time (Europe/Rome)",
      contractLabel: "Contract",
      contractMismatch: "Contract version mismatch",
      status: {
        live: "live",
        degraded: "degraded",
        offline: "offline",
      },
      languageLabel: "Language",
    },
    home: {
      heading: "Select a view for the scenario",
      subheading: "Same verified findings, three dedicated views separated by recipient.",
      scenarioActive: "Configured scenario",
      cards: {
        operator: {
          title: "Operator",
          description:
            "Control room: findings with provenance, vehicle map, SSE rule timeline, conflicts, relevance and reasoning log.",
          cta: "Open control room",
        },
        tourist: {
          title: "Tourist",
          description:
            "Bilingual view (IT/EN): primary recommendation, ranked alternatives and compact area map.",
          cta: "Open tourist view",
        },
        citizen: {
          title: "Citizen",
          description:
            "Recommended public service, qualitative zone status without internal metrics, and nearby map.",
          cta: "Open citizen view",
        },
      },
    },
    provenance: {
      real: "Real",
      simulated: "SIMULATED",
      unavailable: "UNAVAILABLE",
      templateText: "template text",
    },
    agents: {
      mobility: "Mobility",
      crowding: "Crowding",
      context: "Context",
    },
    targets: {
      operator: "Operator",
      tourist: "Tourist",
      citizen: "Citizen",
    },
    operator: {
      title: "Control room",
      findingsTitle: "Agent findings",
      timelineTitle: "Rule timeline (SSE)",
      mapTitle: "Vehicles & zones map",
      decisionTitle: "Decision",
      planTitle: "Plan by recipient",
      relevanceTitle: "Relevance & contributions",
      reasoningTitle: "Reasoning log",
      metricsTitle: "Observable metrics",
      repeatButton: "Repeat decision",
      repeatLoading: "Checking...",
      repeatSame: "same",
      repeatDifferent: "different",
      streamUnavailable: "Stream unavailable",
      streamRetry: "Retry stream",
      streamEmpty: "Waiting for trace events...",
      noRulesBanner: "No rules fired: monitoring plan active with no conflicts.",
      conflictDetected: "Conflict detected",
      noConflict: "No conflict",
      ruleFired: "Fired",
      ruleNotFired: "Not fired",
      confidence: "Confidence",
      source: "Source",
      reference: "Reference",
      density: "Density",
      congestion: "Congestion",
      zone: "Zone",
      heavyRain: "Heavy rain",
      yes: "Yes",
      no: "No",
      attendance: "Expected attendance",
      missingCardNote: "Data unavailable for this agent",
      metricSteps: "Reasoning log steps",
      metricTargets: "Target coverage",
      metricActions: "Plan items",
      metricSimulated: "Simulated findings",
      metricLatency: "Delta finding → decision",
    },
    tourist: {
      title: "Tourist guide",
      subtitle: "Essential guidance on how to get there and what to do now",
      primaryRecommendation: "Primary recommendation",
      alternativesTitle: "Recommended alternatives",
      estimatedTime: "Estimated time",
      moreActions: (count: number) => `${count} more actions`,
      simulatedNotice: "Notice: relies on simulated data",
      noActions: "No tourist actions available for this scenario.",
    },
    citizen: {
      title: "Citizen guide",
      subtitle: "Recommended public transit service and area status",
      primaryRecommendation: "Primary recommendation",
      publicServiceTitle: "Public service",
      zoneStateTitle: "Zone status",
      zoneVeryCrowded: "Very crowded area",
      zoneElevated: "Elevated crowd level",
      zoneNormal: "Regular crowd level",
      moreServicesTitle: "Other service options",
      simulatedNotice: "Notice: relies on simulated data",
      noActions: "No citizen service guidance available for this scenario.",
    },
    map: {
      notConfiguredTitle: "Map not configured",
      notConfiguredDetail:
        "Set NEXT_PUBLIC_MAPBOX_TOKEN to enable the Mapbox view. Vehicle and zone details remain readable below.",
      vehiclesTitle: "Vehicle positions",
      noVehicles: "No vehicle positions available.",
      zonesTitle: "Highlighted zones (geo-fence)",
      noHighlightedZone: "No zone highlighted by findings.",
      routeLabel: "Route",
      ageLabel: "Data age",
      lastObserved: "Last observed",
    },
    states: {
      retry: "Retry",
      knownScenarios: "Configured scenarios",
      requestedScenario: "Requested scenario",
      notFoundTitle: "Scenario not found",
      degradedStream: "SSE stream unavailable: existing decision remains valid.",
      degradedBackend: "Backend unreachable",
      degradedUpstream: "External source unreachable",
      contractMismatchTitle: "Unexpected contract version",
      contractMismatchDetail: "Unknown fields remain read-only and are not interpreted.",
      invalidFinding: "Non-compliant data",
      agentMismatch: "Data does not belong to this agent",
      missingFinding: "No findings available",
      agentRefusal: "Data unavailable",
      configInvalid: "Invalid backend configuration",
      internalError: "Internal service error",
    },
  },
};

export function getDict(locale: Locale): Dictionary {
  return DICTIONARY[locale];
}
