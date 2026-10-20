// Imatinib in ABL1 (PDB 2HYY) with 3Dmol, the same library the app uses.
// palette: { carbon, pocket, n, o, s, hbond, trace, label, labelBg }
window.mountComplex = function mountComplex(el, palette, initialMode = "site", data = window.COMPLEX) {
  const hex = (c) => parseInt(c.replace("#", ""), 16);
  const elem = (carbon) => ({ prop: "elem", map: { C: hex(carbon), N: hex(palette.n), O: hex(palette.o), S: hex(palette.s), H: 0xffffff } });
  const lines = data.pdb.split("\n");
  const ligandPdb = lines.filter((l) => l.startsWith("HETATM")).join("\n");
  const pocketPdb = lines.filter((l) => l.startsWith("ATOM")).join("\n");

  const viewer = $3Dmol.createViewer(el, { antialias: true });
  viewer.setBackgroundColor(0x000000, 0);
  const ligand = viewer.addModel(ligandPdb, "pdb");
  const pocket = viewer.addModel(pocketPdb, "pdb");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function trace(opacity, radius) {
    const t = data.trace;
    for (let i = 1; i < t.length; i++) {
      const a = t[i - 1].xyz, b = t[i].xyz;
      if (t[i].chain !== t[i - 1].chain || Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) > 4.5) continue;
      viewer.addCylinder({ start: { x: a[0], y: a[1], z: a[2] }, end: { x: b[0], y: b[1], z: b[2] }, radius, color: hex(palette.trace), opacity, fromCap: 1, toCap: 1 });
    }
  }

  function setMode(mode) {
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    ligand.setStyle({}, { stick: { radius: 0.2, colorscheme: elem(palette.carbon) }, sphere: { scale: 0.22, colorscheme: elem(palette.carbon) } });
    pocket.setStyle({}, {});
    if (mode === "site" || mode === "protein") {
      pocket.setStyle({}, { stick: { radius: 0.11, opacity: mode === "site" ? 0.9 : 0.5, colorscheme: elem(palette.pocket) } });
    }
    if (mode === "site") {
      data.hbonds.forEach((h) => {
        viewer.addCylinder({ start: { x: h.from[0], y: h.from[1], z: h.from[2] }, end: { x: h.to[0], y: h.to[1], z: h.to[2] }, radius: 0.07, dashed: true, dashLength: 0.22, gapLength: 0.16, color: hex(palette.hbond) });
        viewer.addLabel(h.label, { position: { x: h.to[0], y: h.to[1], z: h.to[2] }, fontSize: 11, fontColor: palette.label, backgroundColor: palette.labelBg, backgroundOpacity: 0.85, borderRadius: 6, padding: 3, inFront: true, font: "sans-serif" });
      });
    }
    if (mode === "protein") trace(0.35, 0.28);
    viewer.zoomTo(mode === "molecule" ? { model: ligand } : {});
    if (mode === "protein") viewer.zoom(0.45);
    if (mode === "site") viewer.zoom(1.15);
    if (mode === "molecule") viewer.zoom(0.8);
    viewer.render();
  }

  setMode(initialMode);
  if (!reduce) viewer.spin("y", 0.35);
  el.addEventListener("pointerdown", () => viewer.spin(false));
  new ResizeObserver(() => { viewer.resize(); viewer.render(); }).observe(el);
  return { setMode, viewer };
};

/** Wires a .mode-switch group to a viewer. */
window.wireModes = function wireModes(group, handle) {
  group.querySelectorAll("button[data-mode]").forEach((b) =>
    b.addEventListener("click", () => {
      group.querySelectorAll("button").forEach((o) => o.setAttribute("aria-pressed", o === b));
      handle.setMode(b.dataset.mode);
    }),
  );
};
