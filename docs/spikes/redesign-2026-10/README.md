# Redesign prototypes (October 2026)

Throwaway HTML prototypes the owner picked the redesign from on 2026-10-19 and 2026-10-20 (#293). They are kept as the reference for #294 to #297, not as code to build on.

The pick is **J2 · Instrument, calmer** on the **D** layout: the chat on the left, an evidence panel on the right, warm grey surfaces, one signal orange and a dark 3D screen.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The switcher: design A to K, answer or start screen, theme, desktop or phone width |
| `a.html`, `b.html`, `c.html` | The first three directions (lab journal, deep field, clinical clean) |
| `d.html` | The chat with the evidence panel, three questions and a ▶ demo of a live answer; the later directions are skins of it (`?skin=`) |
| `skins.css` | The colours and details of every skin; J2 is `lab` with `calm` |
| `content.js` | The real store data for imatinib and dasatinib the pages show |
| `viewer.js` | The 3D view (3Dmol.js) the pages share |
| `prep.py` | Writes the complex data the 3D views load |

## Make the data

The 3D views load `complex-*.js` files, which are git-ignored. Make them from the built store (`data/build/`, see `docs/data-plan.md`), from this folder:

```sh
python prep.py ../../../data/build/structures/complexes/5291.json imatinib
python prep.py ../../../data/build/structures/complexes/3062316.json dasatinib
python prep.py ../../../data/build/structures/complexes/3062316.json
```

The last one writes `complex-data.js`, the dasatinib complex that A to C show.

## Open it

```sh
python -m http.server 8765 --bind 127.0.0.1
```

Then open:

- `http://127.0.0.1:8765/index.html?design=l` for J2 in the switcher
- `http://127.0.0.1:8765/d.html?skin=lab&calm=1` for J2 alone
- `http://127.0.0.1:8765/d.html?skin=lab&calm=1&autoplay=1` for the live demo

The prototypes load their fonts from Google Fonts and 3Dmol.js from jsDelivr, so they need the network. The app bundles its fonts and works offline.
