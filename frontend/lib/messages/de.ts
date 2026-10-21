import type { Messages } from "./en";

/** The interface text in German, addressing the reader as "Sie" like the guard's German answers. */
export const de: Messages = {
  locale: "de-DE",
  language: {
    switch: "Sprache",
    en: "English",
    de: "Deutsch",
  },
  header: {
    thisChat: (usage) => `Dieser Chat: ${usage}`,
    supportedDrugs: "Unterstützte Medikamente",
    benchmarks: "Benchmarks",
  },
  chat: {
    intro: "Fragen Sie zu Medikamenten: wofür sie sind, wie sie wirken und woran sie binden.",
    conversation: "Unterhaltung",
    evidence: "Belege",
    close: "Schließen",
    historyOff:
      "Der Verlauf ist in diesem Browser aus, deshalb wird dieser Chat nicht gespeichert.",
    unavailable: "Der Chat ist gerade nicht verfügbar. Versuchen Sie es später noch einmal.",
    failed: "Beim Antworten ist etwas schiefgegangen. Versuchen Sie es noch einmal.",
  },
  composer: {
    label: "Zu einem Medikament fragen",
    placeholder: "Ihre Frage, z. B. Wie wirkt Imatinib?",
    send: "Senden",
    stop: "Stopp",
    tooLong: (length, max) => `Die Frage ist zu lang: ${length} von höchstens ${max} Zeichen.`,
  },
  disclaimer: {
    before:
      "Molecula ist ein KI-Assistent und kann Fehler machen. Es ist keine medizinische Beratung. Prüfen Sie die offizielle Fachinformation auf",
    link: "DailyMed",
    after: "und fragen Sie Ihren Arzt oder Apotheker, bevor Sie sich nach etwas von hier richten.",
  },
  help: {
    open: "Hilfe",
    title: "So benutzen Sie Molecula",
    close: "Schließen",
    canAsk: "Was Sie fragen können",
    topics: [
      {
        title: "Wie ein Medikament wirkt",
        description: "Wofür es ist und wie es im Körper wirkt.",
        examples: ["Wie wirkt Imatinib?", "Wofür wird Atorvastatin verwendet?"],
      },
      {
        title: "Zielproteine",
        description: "Die Proteine, an die ein Medikament bindet, aus ChEMBL.",
        examples: ["Woran bindet Sildenafil?", "Auf welche Zielproteine wirkt Celecoxib?"],
      },
      {
        title: "3D-Strukturen",
        description: "Das Medikament in der Tasche seines Zielproteins, aus der Protein Data Bank.",
        examples: ["Zeig mir Oseltamivir an seinem Zielprotein in 3D."],
      },
      {
        title: "Fakten aus der Fachinformation, mit Quellen",
        description:
          "Warnhinweise, Nebenwirkungen und Wechselwirkungen aus der FDA-Fachinformation.",
        examples: [
          "Was sind die häufigen Nebenwirkungen von Metformin?",
          "Wovor warnt die Fachinformation von Warfarin?",
        ],
      },
    ],
    wontAnswerTitle: "Was Molecula nicht beantwortet",
    wontAnswer: [
      "Wie viel von einem Medikament Sie persönlich nehmen sollten oder ob Sie eines anfangen oder absetzen sollten. Fragen Sie Ihren Arzt oder Apotheker.",
      "Dosen, die jemandem schaden sollen.",
      "Wie man ein Medikament herstellt.",
    ],
    emergency:
      "Wenn jemand zu viel von einem Medikament genommen haben könnte, rufen Sie jetzt Ihre örtliche Notrufnummer (911 in den USA, 112 in der EU) oder einen Giftnotruf an.",
    sourcesTitle: "Woher die Antworten kommen",
    sources: {
      before:
        "Fakten aus der Fachinformation kommen aus den englischen FDA-Fachinformationen (derselbe Text wie auf DailyMed), chemische Daten aus PubChem, Zielproteine aus ChEMBL und 3D-Strukturen aus der Protein Data Bank. Molecula antwortet nur zu den",
      link: "unterstützten Medikamenten",
      after: ".",
    },
    tags: "Ein kleines Schild nach einem Fakt, etwa „Gleevec · Warnings and cautions“, nennt den Abschnitt der Fachinformation, aus dem er stammt. Die Abschnitte heißen wie in der englischen Fachinformation. Zeigen Sie darauf, um die Textstelle zu lesen, oder klicken Sie, um sie mit den anderen Quellen der Antwort zu sehen. Prüfen Sie die Textstelle, bevor Sie sich auf den Fakt verlassen.",
    panel:
      "Die Belege einer Antwort stehen in einem Bereich neben dem Chat, auf dem Handy in einem Blatt von unten: die 3D-Ansicht, die Quellen mit einem Link zu jeder Fachinformation auf DailyMed und die Schritte, die Molecula gemacht hat. Der Bereich folgt der Frage, zu der Sie scrollen, und die Knöpfe unter jeder Frage öffnen ihn bei dieser Antwort. Während Sie eine frühere Antwort lesen, bringt „Laufende Antwort“ Sie zu der zurück, die gerade entsteht. Klicken Sie auf einen Schritt, um zu sehen, was er gefunden hat: die Textstellen, die Eigenschaften, die Zielproteine oder den 3D-Komplex.",
  },
  model: {
    local: "lokal",
  },
  usage: {
    tokens: (count) => `${count} Tokens`,
    tokensUnknown: "Tokens unbekannt",
    costUnknown: "Kosten unbekannt",
  },
  exportMenu: {
    open: "Chat exportieren",
    json: "JSON, mit Quellen und Werkzeugen",
    csv: "CSV, eine Zeile pro Nachricht",
    preparing: "Die 3D-Bilder werden vorbereitet…",
    print: "Drucken oder als PDF speichern",
  },
  navigator: {
    label: "Fragen in diesem Chat",
    question: (number, question) => `Frage ${number}: ${question}`,
  },
  sidebar: {
    chats: "Chats",
    show: "Chats zeigen",
    hide: "Chats ausblenden",
    open: "Chats öffnen",
    close: "Chats schließen",
    newChat: "Neuer Chat",
    benchmarks: "Benchmarks",
    dashboard: "Dashboard",
    howItAnswers: "So antwortet es",
    mcpServer: "MCP-Server",
    settings: "Einstellungen",
    history: "Chatverlauf",
    historyAnswering: "Chatverlauf, eine Antwort kommt gerade",
    bookmarks: "Lesezeichen",
    answering: (title) => `${title}, antwortet gerade`,
    allBookmarks: (count) => `Alle ${count} Lesezeichen`,
    groups: {
      Bookmarked: "Mit Lesezeichen",
      Today: "Heute",
      Yesterday: "Gestern",
      Earlier: "Früher",
    },
    savedHere: "Nur in diesem Browser gespeichert.",
    noChats: "Noch keine Chats",
    noChatsText:
      "Ihre Fragen erscheinen hier, benannt nach der ersten Frage. Sie werden nur in diesem Browser gespeichert, nicht auf einem Server.",
    removedBefore: "„",
    removedAfter: "“ aus den Lesezeichen entfernt",
    undo: "Rückgängig",
    historyOffTitle: "Der Verlauf ist in diesem Browser aus",
    historyOffText:
      "Der Browser lässt Molecula keine Chats speichern (ein privates Fenster, oder der Speicher ist voll). Der Chat funktioniert trotzdem; diese Unterhaltung ist weg, wenn Sie den Tab schließen.",
  },
  settings: {
    title: "Einstellungen",
    close: "Schließen",
    model: "Modell, das die Antworten schreibt",
    loading: "Die Modelle werden geladen…",
    off: "Der Chat ist aus, deshalb gibt es kein Modell zur Auswahl.",
    local: "lokal",
    cloud: "Cloud",
    tested: "getestet",
    default: "Standard",
    developedWith:
      "Molecula wurde mit gpt-oss-20b entwickelt, das jeden Prompt, jede Sicherheitsregel und jede Auswertung durchlaufen hat, und gpt-6-luna wurde als Cloud-Modell gemessen. Ein anderes Modell kann hier schlechter abschneiden. Es kann ein Nachschlagen auslassen und aus dem Gedächtnis antworten oder die falsche Quelle zitieren.",
    checksStay:
      "Welches Modell Sie auch wählen, die Sicherheitsprüfung vor der Antwort und die Quellenprüfung danach bleiben bei den Modellen, mit denen sie getestet wurden.",
    loadsFirst:
      "Ein lokales Modell wird auf dem lokalen Server geladen, wenn es zum ersten Mal gefragt wird, was eine Minute dauern kann",
    fitsNextTo: (model) => `, und es muss neben ${model} in den Speicher passen`,
    context:
      ". Laden Sie es mit mindestens 32k Tokens Kontext: Eine Antwort mit einer Suche in den Fachinformationen braucht schon etwa 9k, mehr als die 8k, die LM Studio vorgibt.",
  },
  historyRow: {
    answering: "Antwortet gerade",
    waiting: "Wartet auf eine andere Antwort",
    bookmark: (title) => `Lesezeichen setzen: ${title}`,
    removeBookmark: (title) => `Lesezeichen entfernen: ${title}`,
    options: (title) => `Optionen: ${title}`,
    rename: "Umbenennen",
    bookmarkItem: "Lesezeichen setzen",
    removeBookmarkItem: "Lesezeichen entfernen",
    delete: "Löschen",
    title: "Titel des Chats",
    renameHint: "Enter speichert · Esc bricht ab",
    deleteChat: "Chat löschen",
    deleteConfirm: "Diesen Chat löschen? Das lässt sich nicht rückgängig machen.",
    cancel: "Abbrechen",
  },
  mcp: {
    title: "Molecula in Ihrem KI-Assistenten nutzen",
    close: "Schließen",
    intro:
      "Die sechs Werkzeuge des Chats sind auch ein MCP-Server. So kann ein Assistent wie Claude Desktop oder ein anderer MCP-Client Medikamente im selben Datenbestand nachschlagen, aus dem dieser Chat antwortet. Jedes Ergebnis nennt seine Quellen mit einer Nummer, unter der man sie zitiert.",
    tools: {
      resolve_drug:
        "Welches unterstützte Medikament ein Name meint: einen Wirkstoff, eine Marke, einen nicht-amerikanischen oder deutschen Namen oder ein Salz.",
      get_properties: "Die chemischen Eigenschaften des Medikaments, aus PubChem.",
      get_targets:
        "Die Proteine, auf die das Medikament wirkt, und sein Wirkmechanismus, aus ChEMBL.",
      get_complex:
        "Die geprüfte 3D-Struktur des Medikaments an seinem Zielprotein, aus der Protein Data Bank, mit den Aminosäuren, die es berühren.",
      search_labels:
        "Textstellen aus den FDA-Fachinformationen: Anwendung, Nebenwirkungen, Warnhinweise, Wechselwirkungen und mehr.",
      compare_drugs: "Die chemischen Eigenschaften von 2 bis 4 Medikamenten nebeneinander.",
    },
    connectTitle: "Claude Desktop verbinden",
    connectOpen: "Öffnen Sie Settings → Developer → Edit Config, fügen Sie dies in",
    connectReplace: " ein, ersetzen Sie",
    connectWith: "durch den Ordner Ihrer Molecula-Kopie und starten Sie Claude Desktop neu.",
    copyConfig: "Konfiguration kopieren",
    otherTitle: "Andere MCP-Clients",
    otherStart: "Starten Sie den Server im Ordner",
    otherFolder: "Ihrer Kopie. Das dauert etwa 30 Sekunden, während er das Embedding-Modell lädt.",
    start: {
      stdio: "Über stdio",
      "Streamable HTTP": "Über Streamable HTTP, unter http://localhost:8001/mcp",
      Docker: "Dasselbe in Docker",
    },
    copyCommand: (name) => `Den ${name}-Befehl kopieren`,
    localBefore: "Der Server läuft auf Ihrem eigenen Computer, neben Ihrer Kopie und mit derselben",
    localAfter:
      "und demselben Datenbestand. Er hat keine Anmeldung und beantwortet nur Anfragen an localhost, deshalb lässt sich ein Molecula, das woanders läuft, nicht verbinden.",
    copy: "Kopieren",
    copied: "Kopiert",
    copyFailed: "Kopieren fehlgeschlagen",
  },
  drugs: {
    back: "← Molecula",
    title: "Unterstützte Medikamente",
    intro:
      "Molecula antwortet nur zu den Medikamenten auf dieser Liste. Suchen Sie nach Wirkstoff, Marke oder einem anderen Namen.",
    search: "Nach Name oder Marke suchen",
    placeholder: "z. B. Tylenol oder Imatinib",
    loading: "Die unterstützten Medikamente werden geladen…",
    failed:
      "Die unterstützten Medikamente konnten nicht geladen werden. Prüfen Sie, ob das Backend läuft, und laden Sie die Seite neu.",
    didYouMean: "Meinten Sie",
    or: " oder ",
    has3d: "3D-Struktur",
    question: (name) => `Wie wirkt ${name}?`,
    supported: (total) =>
      `${total} ${total === 1 ? "unterstütztes Medikament" : "unterstützte Medikamente"}`,
    pickOne: (supported) => `${supported}. Wählen Sie eines, um zu fragen, wie es wirkt.`,
    underAnotherName: (searched) => `„${searched}“ wird unter einem anderen Namen unterstützt.`,
    notSupported: (searched, supported) =>
      `„${searched}“ wird nicht unterstützt. Molecula antwortet nur zu seinen ${supported}.`,
    matches: (count, supported, searched) =>
      `${count} von ${supported} ${count === 1 ? "passt" : "passen"} zu „${searched}“.`,
  },
  evidence: {
    answerOf: (number, total) => `Antwort ${number} von ${total}`,
    live: "Laufende Antwort",
    previous: "Vorige Antwort",
    next: "Nächste Antwort",
    tab3d: "3D",
    tabSources: "Quellen",
    tabSteps: "Schritte",
    tabFlow: "Ablauf",
    fresh: ", neu",
    thinking: "Denkt nach…",
    noLookup: "Molecula hat das beantwortet, ohne etwas nachzuschlagen.",
    drugIn3d: "Medikament in 3D",
    lookingUp: "Schlägt nach… eine Struktur erscheint hier, wenn diese Antwort eine findet.",
    noStructure: "Diese Antwort hat keine Struktur nachgeschlagen.",
    structuresInChat: "Strukturen in diesem Chat",
    molecule: "Molekül",
    answer: (number) => `Antwort ${number}`,
    sourcesLater: "Die Quellen erscheinen hier, sobald die Antwort geschrieben ist.",
    noSources: "Diese Antwort hat keine Quellen.",
    usedNoSources: "Diese Antwort hat keine Quellen benutzt.",
    sourcesOfAnswer: "Quellen dieser Antwort",
    cited: "Zitiert",
  },
  sources: {
    labelOf: (date) => `US-Fachinformation (englisch) vom ${date}`,
    openLabel: "Die Fachinformation auf DailyMed öffnen (englisch)",
    openOn: (site) => `Auf ${site} öffnen`,
    found: "Von der Quellenprüfung gefunden",
    sources: "Quellen",
    foundNote: "Die Antwort hat das nicht zitiert; die Quellenprüfung hat den Satz hier gefunden.",
    openFdaBefore: "Daten bereitgestellt von der U.S. Food and Drug Administration (",
    openFdaAfter: ")",
  },
  pills: {
    writing: "Schreibt die Antwort",
    thinking: "Denkt nach",
    steps: (count) => `${count} ${count === 1 ? "Schritt" : "Schritte"}`,
    sources: (count) => `${count} ${count === 1 ? "Quelle" : "Quellen"}`,
    molecule: "Molekül",
    no3d: "kein 3D",
  },
  turn: {
    query: "Frage",
    waiting: "Wartet, bis die Antwort in einem anderen Chat fertig ist…",
    stopped: "Gestoppt.",
    tryAgain: "Noch einmal versuchen",
    didYouMean: "Meinten Sie",
    whatIs: (name) => `Was ist ${name}?`,
  },
};
