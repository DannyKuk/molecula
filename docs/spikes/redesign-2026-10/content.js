// Throwaway design prototype. Content is the real store data for imatinib (CID 5291):
// Gleevec label of 2026-07-13, ChEMBL targets, PDB 2HYY. The answer text is hand-written.
window.M = (() => {
  const LABEL_URL =
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=211ef2da-2868-4a77-8055-1cb2cd78e24b";

  const sources = {
    1: {
      kind: "label",
      label: "Gleevec · Mechanism of action",
      date: "July 13, 2026",
      url: LABEL_URL,
      text: "Imatinib mesylate is a protein-tyrosine kinase inhibitor that inhibits the BCR-ABL tyrosine kinase, the constitutive abnormal tyrosine kinase created by the Philadelphia chromosome abnormality in CML. Imatinib inhibits proliferation and induces apoptosis in BCR-ABL positive cell lines as well as fresh leukemic cells from Philadelphia chromosome positive chronic myeloid leukemia…",
    },
    2: {
      kind: "label",
      label: "Gleevec · Indications and usage",
      date: "July 13, 2026",
      url: LABEL_URL,
      text: "Gleevec is a kinase inhibitor indicated for the treatment of: Newly diagnosed adult and pediatric patients with Philadelphia chromosome positive chronic myeloid leukemia (Ph+ CML) in chronic phase… Adult patients with relapsed or refractory Philadelphia chromosome positive acute lymphoblastic leukemia (Ph+ ALL)…",
    },
    3: {
      kind: "label",
      label: "Gleevec · Mechanism of action",
      date: "July 13, 2026",
      url: LABEL_URL,
      text: "Imatinib is also an inhibitor of the receptor tyrosine kinases for platelet-derived growth factor (PDGF) and stem cell factor (SCF), c-Kit, and inhibits PDGF- and SCF-mediated cellular events.",
    },
    4: {
      kind: "page",
      label: "ChEMBL · Tyrosine-protein kinase ABL1",
      site: "ChEMBL",
      url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1862",
    },
    5: {
      kind: "page",
      label: "RCSB PDB · 2HYY",
      site: "RCSB PDB",
      url: "https://www.rcsb.org/structure/2HYY",
    },
    6: {
      kind: "page",
      label: "PubChem · imatinib",
      site: "PubChem",
      url: "https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    },
  };

  // Strings are text (with **bold**); arrays are citations.
  const answer = [
    [
      "Imatinib (Gleevec) is a **kinase inhibitor**. It blocks **BCR-ABL**, the abnormal tyrosine kinase that the Philadelphia chromosome creates in chronic myeloid leukemia (CML). Blocking it stops the leukemic cells from multiplying and makes them die off.",
      [1],
    ],
    [
      "It also blocks two receptor kinases: the ones for platelet-derived growth factor (PDGF) and for stem cell factor (c-Kit).",
      [3, 4],
    ],
    [
      "That is why it is used for Philadelphia-chromosome-positive CML and acute lymphoblastic leukemia (ALL), among other cancers.",
      [2],
    ],
    [
      "**In 3D:** in PDB 2HYY, imatinib sits deep in the ATP pocket of ABL1, held by six hydrogen bonds, among them Met318 and Thr315.",
      [5],
    ],
  ];

  const targets = [
    { name: "Tyrosine-protein kinase ABL1", mech: "Tyrosine-protein kinase ABL inhibitor", meta: "Homo sapiens · single protein", genes: ["ABL1"] },
    { name: "Bcr/Abl fusion protein", mech: "Bcr/Abl fusion protein inhibitor", meta: "Homo sapiens · chimeric protein", genes: ["ABL1", "BCR"] },
    { name: "Platelet-derived growth factor receptor beta", mech: "PDGFR-beta inhibitor", meta: "Homo sapiens · single protein", genes: ["PDGFRB"] },
    { name: "Mast/stem cell growth factor receptor Kit", mech: "Stem cell growth factor receptor inhibitor", meta: "Homo sapiens · single protein", genes: ["KIT"] },
  ];

  const steps = [
    { text: "Looking up imatinib", summary: "“imatinib” → imatinib", icon: "search", card: "drug" },
    { text: "Finding the targets of imatinib", summary: "4 targets", icon: "target", card: "targets" },
    { text: "Searching the imatinib label", summary: "5 passages", icon: "label", card: "labels" },
    { text: "Looking up the 3D complex of imatinib", summary: "2HYY · ABL1 (BCR-ABL)", icon: "cube", card: "complex" },
  ];

  const hbonds = [
    ["Ile360", "A", "O – N3", "2.72"],
    ["Met318", "A", "N – N1", "2.94"],
    ["Asp381", "A", "N – O1", "2.98"],
    ["Thr315", "A", "OG1 – N4", "3.01"],
    ["Glu286", "A", "OE2 – N5", "3.09"],
    ["His361", "A", "O – N3", "3.12"],
  ];

  const properties = [
    ["Formula", "C₂₉H₃₁N₇O"],
    ["Molecular weight", "493.6 g/mol"],
    ["XLogP", "3.5"],
    ["Polar surface", "86.3 Å²"],
    ["H-bond donors / acceptors", "2 / 7"],
    ["Rotatable bonds", "7"],
  ];

  const topics = [
    { title: "How a drug works", icon: "spark", desc: "What it is for and how it acts in the body.", examples: ["How does imatinib work?", "What is atorvastatin used for?"] },
    { title: "Targets", icon: "target", desc: "The proteins a drug binds to, from ChEMBL.", examples: ["What does sildenafil bind to?", "Which targets does celecoxib act on?"] },
    { title: "3D structures", icon: "cube", desc: "The drug bound in its target's pocket, from the Protein Data Bank.", examples: ["Show oseltamivir bound to its target in 3D."] },
    { title: "Label facts, with sources", icon: "label", desc: "Warnings, side effects and interactions from the FDA drug label.", examples: ["What are the common side effects of metformin?", "What does the warfarin label warn about?"] },
  ];

  const wontAnswer = [
    "How much of a medicine you personally should take, or whether to start or stop one.",
    "Doses meant to harm someone.",
    "How to make a drug.",
  ];

  const chats = [
    { group: "Bookmarked", items: [{ title: "Sildenafil targets", bookmark: true }] },
    {
      group: "Today",
      items: [
        { title: "How does imatinib work?", active: true },
        { title: "Side effects of metformin" },
        { title: "Oseltamivir in 3D" },
      ],
    },
    {
      group: "Yesterday",
      items: [{ title: "Ibuprofen vs naproxen" }, { title: "What the warfarin label warns about" }],
    },
  ];

  const icons = {
    search: '<path d="m21 21-4.3-4.3"/><circle cx="11" cy="11" r="7"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    label: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    cube: '<path d="m21 16-9 5-9-5V8l9-5 9 5z"/><path d="m3.3 7.5 8.7 5 8.7-5M12 22V12.5"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17.5v.01"/>',
    pill: '<rect x="2" y="8" width="20" height="8" rx="4" transform="rotate(-35 12 12)"/><path d="m9 8.5 6 7"/>',
    expand: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
    replay: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    bookmark: '<path d="M19 21l-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
    ext: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    atom: '<circle cx="12" cy="12" r="1.5"/><ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/>',
    phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  };

  const icon = (name, cls = "ic") =>
    `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;

  const bold = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  /** The answer as paragraphs; `chip(refs, labels)` renders one citation run. */
  function answerHTML(chip) {
    return answer
      .map((parts) => {
        const html = parts
          .map((part) => {
            if (typeof part === "string") return bold(part);
            const labels = [...new Set(part.map((r) => sources[r].label))];
            return chip(part, labels);
          })
          .join(" ");
        return `<p>${html}</p>`;
      })
      .join("");
  }

  function popoverHTML(refs) {
    return refs
      .map((r) => {
        const s = sources[r];
        if (s.kind === "label")
          return `<div class="pop-item"><div class="pop-title">${s.label}</div><div class="pop-meta">FDA label of ${s.date}</div><div class="pop-text">${s.text}</div><a class="pop-link" href="${s.url}" target="_blank" rel="noopener">Open the label on DailyMed ${icon("ext", "ic ic-xs")}</a></div>`;
        return `<div class="pop-item"><div class="pop-title">${s.label}</div><a class="pop-link" href="${s.url}" target="_blank" rel="noopener">Open on ${s.site} ${icon("ext", "ic ic-xs")}</a></div>`;
      })
      .join("");
  }

  function cardHTML(kind) {
    if (kind === "drug")
      return `<p>“imatinib” is the generic name of <strong>imatinib</strong> (PubChem CID 5291).</p><dl class="kv">${properties.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl><p><a class="src-link" href="${sources[6].url}" target="_blank">PubChem ${icon("ext", "ic ic-xs")}</a></p>`;
    if (kind === "targets")
      return `<ul class="targets">${targets
        .map(
          (t) =>
            `<li><div class="t-name">${t.name}</div><div class="t-mech">${t.mech}</div><div class="t-meta">${t.meta} · genes ${t.genes.map((g) => `<code>${g}</code>`).join(" ")}</div></li>`,
        )
        .join("")}</ul><p><a class="src-link" href="${sources[4].url}" target="_blank">ChEMBL ${icon("ext", "ic ic-xs")}</a></p>`;
    if (kind === "labels")
      return `<p class="muted">Searched for “how does imatinib work” in the Gleevec label.</p><ul class="passages">${[
        [1, "Mechanism of action", true],
        [2, "Indications and usage", true],
        [3, "Mechanism of action", true],
        [7, "Clinical pharmacology", false],
        [8, "Description", false],
      ]
        .map(([n, sec, cited]) => `<li><span class="p-num">[${n}]</span> Gleevec · ${sec} <span class="muted">· Jul 13, 2026</span>${cited ? '<span class="cited">cited</span>' : ""}</li>`)
        .join("")}</ul>`;
    if (kind === "complex")
      return `<dl class="kv"><dt>Target</dt><dd>ABL1 (BCR-ABL)</dd><dt>Organism</dt><dd>Homo sapiens</dd><dt>Structure</dt><dd><a class="src-link" href="${sources[5].url}" target="_blank">PDB 2HYY</a></dd><dt>Drug's code</dt><dd><code>STI</code></dd></dl><div class="h4">Hydrogen bonds</div><table class="hb"><thead><tr><th>Residue</th><th>Chain</th><th>Atoms (protein – drug)</th><th>Distance</th></tr></thead><tbody>${hbonds
        .map(([r, c, a, d]) => `<tr><td>${r}</td><td>${c}</td><td><code>${a}</code></td><td class="num">${d} Å</td></tr>`)
        .join("")}</tbody></table>`;
    return "";
  }

  return { sources, answer, steps, targets, topics, wontAnswer, chats, hbonds, properties, icon, answerHTML, popoverHTML, cardHTML };
})();

/** Theme and screen come from the shell's query string. */
(() => {
  const q = new URLSearchParams(location.search);
  const theme = q.get("theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.screen = q.get("screen") === "start" ? "start" : "answer";
})();

/** Citation popovers, collapsibles and the 3D mode switch, shared by every design. */
window.wire = function wire(root = document) {
  let pop = null;
  let pinned = false;
  const close = () => {
    pop?.remove();
    pop = null;
    pinned = false;
  };
  const open = (chip, pin) => {
    close();
    pop = document.createElement("div");
    pop.className = "pop";
    pop.innerHTML = M.popoverHTML(chip.dataset.refs.split(",").map(Number));
    document.body.appendChild(pop);
    const r = chip.getBoundingClientRect();
    const w = Math.min(340, innerWidth - 24);
    pop.style.width = w + "px";
    pop.style.left = Math.max(12, Math.min(r.left, innerWidth - w - 12)) + scrollX + "px";
    pop.style.top = r.bottom + 8 + scrollY + "px";
    pinned = pin;
    pop.addEventListener("mouseleave", () => !pinned && close());
  };
  root.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("mouseenter", () => !pinned && open(chip, false));
    chip.addEventListener("mouseleave", (e) => {
      if (!pinned && pop && !pop.contains(e.relatedTarget)) setTimeout(() => !pinned && !pop?.matches(":hover") && close(), 120);
    });
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      open(chip, true);
    });
  });
  document.addEventListener("click", (e) => pop && !pop.contains(e.target) && close());
  root.querySelectorAll("[data-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const target = btn.dataset.toggle ? root.querySelector(btn.dataset.toggle) : btn.closest("[data-collapsible]");
      const isOpen = target.classList.toggle("open");
      btn.setAttribute("aria-expanded", isOpen);
    }),
  );
  return { openChip: (chip) => open(chip, true) };
};
