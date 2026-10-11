"""
Molecula data check: queries the real sources the app would use and reports what comes back.

  pip install requests rdkit biotite
  python check_data.py            (from inside the molecula-prototype folder, so it can compare with the demo files)

Writes report.md and the raw responses to ./raw/. Takes about a minute (PubChem allows ~5 requests/s).
"""
import io, json, os, sys, time
import requests

RAW = "raw"; os.makedirs(RAW, exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "molecula-data-check/0.1"
REPORT = []
def out(line=""): print(line); REPORT.append(line)
def ok(m): out(f"  OK    {m}")
def warn(m): out(f"  WARN  {m}")
def fail(m): out(f"  FAIL  {m}")
def save(name, content):
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(os.path.join(RAW, name), mode) as f: f.write(content)

def get(url, **kw):
    """GET with polite pacing and retries: PubChem answers 503 when it throttles."""
    delay = 1.0
    for attempt in range(6):
        time.sleep(0.4 if "pubchem" in url else 0.25)
        try:
            r = S.get(url, timeout=30, **kw)
        except requests.RequestException as e:
            class R: status_code = 0; text = str(e); content = b""
            r = R()
        if r.status_code not in (0, 429, 503): return r
        wait = float(getattr(r, "headers", {}).get("Retry-After", delay)) if hasattr(r, "headers") else delay
        print(f"        (HTTP {r.status_code}, retrying in {wait:.0f}s)")
        time.sleep(wait); delay = min(delay * 2, 20)
    return r

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Crippen
except ImportError:
    Chem = None

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# ---------------------------------------------------------------- 1. PubChem
out("# Molecula data check\n")
out("## 1. PubChem: names, salts, properties, 3D structures\n")
# (query as a user might type it, what we expect)
NAMES = [
    ("Gleevec", "imatinib, brand name, sold as a salt"),
    ("imatinib", "generic name"),
    ("caffeine", "simple"),
    ("ibuprofen", "racemic mixture"),
    ("Tylenol", "US brand name for paracetamol"),
    ("paracetamol", "non-US generic name"),
    ("Aspirin", "everyday"),
    ("atorvastatin", "larger drug, 41 heavy atoms"),
    ("cetirizine", "antihistamine"),
    ("Ibuflam", "German brand, probably unknown to PubChem"),
    ("insulin", "protein, no small-molecule 3D expected"),
    ("semaglutide", "peptide drug, too big/flexible for PubChem 3D"),
]
PROPS = "MolecularFormula,MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,InChIKey,SMILES"
pubchem = {}
for name, note in NAMES:
    out(f"### {name}  ({note})")
    r = get(f"{PUG}/compound/name/{requests.utils.quote(name)}/cids/JSON")
    if r.status_code != 200:
        fail(f"name not resolved (HTTP {r.status_code})"); out(); continue
    cids = r.json().get("IdentifierList", {}).get("CID", [])
    cid = cids[0]
    ok(f"resolved to CID {cid}" + (f" ({len(cids)} candidates)" if len(cids) > 1 else ""))
    # parent compound (strips salts like mesylate)
    r = get(f"{PUG}/compound/cid/{cid}/cids/JSON", params={"cids_type": "parent"})
    parent = cid
    if r.status_code != 200:
        warn(f"could not check for a parent compound (HTTP {r.status_code}); properties below may describe a salt")
    if r.status_code == 200:
        p = r.json().get("IdentifierList", {}).get("CID", [cid])
        parent = p[0] if p else cid
        if parent != cid: warn(f"CID {cid} is a salt or mixture, parent compound is CID {parent}. The app must switch to the parent.")
    r = get(f"{PUG}/compound/cid/{parent}/property/{PROPS}/JSON")
    if r.status_code == 400:  # older property name
        r = get(f"{PUG}/compound/cid/{parent}/property/{PROPS.replace('SMILES','IsomericSMILES')}/JSON")
    props = {}
    if r.status_code == 200:
        props = r.json()["PropertyTable"]["Properties"][0]; save(f"pubchem_{name}_props.json", r.text)
        ok("properties: " + ", ".join(f"{k}={props.get(k)}" for k in ["MolecularFormula","MolecularWeight","XLogP","TPSA","HBondDonorCount","HBondAcceptorCount","RotatableBondCount","HeavyAtomCount"]))
    else:
        fail(f"properties request failed (HTTP {r.status_code})")
    r = get(f"{PUG}/compound/cid/{parent}/SDF", params={"record_type": "3d"})
    has3d = r.status_code == 200 and "V2000" in r.text
    if has3d:
        save(f"pubchem_{name}_3d.sdf", r.text)
        n = None
        if Chem:
            m = Chem.MolFromMolBlock(r.text, removeHs=False); n = m.GetNumAtoms() if m else None
        ok(f"3D conformer available" + (f" ({n} atoms incl. hydrogens)" if n else ""))
    else:
        warn(f"no PubChem 3D conformer (HTTP {r.status_code}). The app needs the RDKit fallback or a 'not supported' answer.")
    pubchem[name] = dict(cid=cid, parent=parent, props=props, has3d=has3d)
    out()

# ---------------------------------------------------------------- 2. PubChem vs demo numbers
out("## 2. Demo numbers vs PubChem\n")
DEMO = {"imatinib": dict(mw=493.6, logp=4.59, tpsa=86.3, hbd=2, hba=7, rotb=7),
        "caffeine": dict(mw=194.2, logp=-1.03, tpsa=61.8, hbd=0, hba=3, rotb=0),
        "ibuprofen": dict(mw=206.3, logp=3.07, tpsa=37.3, hbd=1, hba=1, rotb=4)}
out("Demo values come from RDKit. logP differs by design: RDKit uses Crippen logP, PubChem uses XLogP3. H-bond acceptor counts also use different rules.\n")
out("| Molecule | MW demo / PubChem | logP demo / PubChem | TPSA | HBD | HBA | Rot. bonds |")
out("|---|---|---|---|---|---|---|")
for k, d in DEMO.items():
    p = pubchem.get(k, {}).get("props", {})
    f = lambda a, b: f"{a} / {p.get(b, '?')}"
    out(f"| {k} | {f(d['mw'],'MolecularWeight')} | {f(d['logp'],'XLogP')} | {f(d['tpsa'],'TPSA')} | {f(d['hbd'],'HBondDonorCount')} | {f(d['hba'],'HBondAcceptorCount')} | {f(d['rotb'],'RotatableBondCount')} |")
out()

# ---------------------------------------------------------------- 3. RCSB PDB
out("## 3. RCSB PDB: can we find drug-protein complexes automatically?\n")
SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
def rcsb(query, return_type):
    time.sleep(0.25)
    try:
        r = S.post(SEARCH, json={"query": query, "return_type": return_type, "request_options": {"return_all_hits": True}}, timeout=30)
    except requests.RequestException as e:
        return None, str(e)
    if r.status_code == 204: return [], None
    if r.status_code != 200: return None, f"HTTP {r.status_code}: {r.text[:200]}"
    return [h["identifier"] for h in r.json().get("result_set", [])], None

def term(attr, value, op="exact_match"):
    return {"type": "terminal", "service": "text", "parameters": {"attribute": attr, "operator": op, "value": value}}

for name, known in [("imatinib", "STI"), ("caffeine", "CFF"), ("ibuprofen", "IBP"), ("Aspirin", "AIN"), ("paracetamol", "TYL")]:
    out(f"### {name}")
    key = pubchem.get(name, {}).get("props", {}).get("InChIKey")
    comps = None
    if key:
        comps, err = rcsb(term("rcsb_chem_comp_descriptor.InChIKey", key), "mol_definition")
        if err: warn(f"InChIKey search failed: {err}")
        elif comps: ok(f"PubChem InChIKey {key} maps to PDB ligand code(s): {', '.join(comps)}")
        else:
            warn(f"exact InChIKey {key} not in PDB (stereo or protonation may differ), trying the connectivity block")
            comps, err = rcsb(term("rcsb_chem_comp_descriptor.InChIKey", key.split('-')[0], "contains_phrase"), "mol_definition")
            if comps: ok(f"connectivity match: {', '.join(comps[:8])}")
            else: warn("no match on connectivity either")
    codes = comps or [known]
    if not comps: out(f"  ...   falling back to the known ligand code {known}")
    entries, err = rcsb(term("rcsb_nonpolymer_instance_feature_summary.comp_id", codes[0]), "entry")
    if err:
        entries, err = rcsb(term("rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id", codes[0]), "entry")
    if err: fail(f"entry search failed: {err}")
    elif entries: ok(f"{len(entries)} PDB entries contain {codes[0]}, e.g. {', '.join(entries[:8])}")
    else: warn(f"no PDB entries contain {codes[0]}")
    out()

# ---------------------------------------------------------------- 4. 1IEP straight from RCSB
out("## 4. 1IEP downloaded from RCSB vs the cleaned file the demo used\n")
r = get("https://files.rcsb.org/download/1IEP.cif")
if r.status_code != 200:
    fail(f"could not download 1IEP.cif (HTTP {r.status_code})")
else:
    save("1IEP.cif", r.text)
    try:
        import numpy as np
        import biotite.structure as struc
        import biotite.structure.io.pdbx as pdbx
        s = pdbx.get_structure(pdbx.CIFFile.read(io.StringIO(r.text)), model=1)
        chains = sorted({str(c) for c in s.chain_id[struc.filter_amino_acids(s)]})
        ligs = s[s.res_name == "STI"]
        lig_chains = sorted({str(c) for c in ligs.chain_id})
        waters = int((s.res_name == "HOH").sum())
        ok(f"raw file: protein chains {chains}, imatinib (STI) copies in chains {lig_chains}, {waters} water atoms, hydrogens present: {bool((s.element == 'H').any())}")
        warn("raw entries need cleaning before display: pick one chain and ligand copy, drop waters and other het groups. The demo file was already cleaned.")
        ch = lig_chains[0]
        lig = ligs[ligs.chain_id == ch]; lig = lig[lig.element != "H"]
        prot = s[struc.filter_amino_acids(s) & (s.chain_id == ch) & (s.element != "H")]
        ok(f"chain {ch}: {len(lig)} ligand heavy atoms, {struc.get_residue_count(prot)} protein residues")
        found = []
        for a in lig:
            if a.element not in ("N", "O"): continue
            for b in prot:
                if b.element in ("N", "O"):
                    d = float(np.linalg.norm(a.coord - b.coord))
                    if d < 3.3: found.append((f"{b.res_name.title()}{b.res_id}", round(d, 2)))
        found = sorted(set(found), key=lambda x: x[1])
        demo = {"Met318", "Thr315", "Glu286", "Asp381", "Ile360", "His361"}
        got = {f for f, _ in found}
        ok("polar contacts < 3.3 Å from the raw file: " + ", ".join(f"{a} {d} Å" for a, d in found))
        if got == demo: ok("identical to the six contacts shown in the demo")
        else: warn(f"differs from the demo. Only in raw: {sorted(got - demo)}; only in demo: {sorted(demo - got)}")
        # coordinates vs demo ligand file
        demo_sdf = os.path.join("data", "1iep_ligand.sdf")
        if Chem and os.path.exists(demo_sdf):
            m = Chem.MolFromMolFile(demo_sdf)
            dx = np.array(m.GetConformer().GetPositions())
            dists = [np.min(np.linalg.norm(dx - c, axis=1)) for c in lig.coord]
            ok(f"demo ligand vs raw ligand: max atom offset {max(dists):.3f} Å (0 means same coordinates)")
        else:
            out("  ...   run from the molecula-prototype folder to compare coordinates with the demo file")
    except ImportError:
        warn("install biotite and numpy to analyse the structure")
out()

# ---------------------------------------------------------------- 5. openFDA labels
out("## 5. openFDA drug labels: what text would the knowledge base get?\n")
SECTIONS = ["indications_and_usage", "mechanism_of_action", "dosage_and_administration", "warnings_and_cautions", "warnings",
            "contraindications", "drug_interactions", "adverse_reactions", "clinical_pharmacology", "do_not_use", "stop_use", "active_ingredient"]
key = os.environ.get("OPENFDA_API_KEY")
for name, field in [("imatinib", "generic_name"), ("ibuprofen", "generic_name"), ("acetaminophen", "generic_name"),
                    ("paracetamol", "generic_name"), ("caffeine", "generic_name"), ("Gleevec", "brand_name")]:
    params = {"search": f'openfda.{field}:"{name}"', "limit": 1}
    if key: params["api_key"] = key
    r = get("https://api.fda.gov/drug/label.json", params=params)
    if r.status_code == 404:
        warn(f"{name}: no label found via {field}"); continue
    if r.status_code != 200:
        fail(f"{name}: HTTP {r.status_code} {r.text[:150]}"); continue
    j = r.json(); save(f"openfda_{name}.json", json.dumps(j, indent=1))
    total = j["meta"]["results"]["total"]; lab = j["results"][0]
    of = lab.get("openfda", {})
    present = [f"{s} ({len(' '.join(lab[s]))} chars)" for s in SECTIONS if s in lab]
    ok(f"{name}: {total} labels match. First: {of.get('brand_name', ['?'])[0]} / {of.get('generic_name', ['?'])[0]}, "
       f"{of.get('product_type', ['?'])[0]}")
    out(f"        sections: {', '.join(present) or 'none of the expected ones'}")
out()
out("### Prescription labels (these carry mechanism of action, OTC labels don't)\n")
for name in ["ibuprofen", "acetaminophen", "caffeine"]:
    params = {"search": f'openfda.generic_name:"{name}" AND openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND _exists_:mechanism_of_action', "limit": 1}
    if key: params["api_key"] = key
    r = get("https://api.fda.gov/drug/label.json", params=params)
    if r.status_code != 200:
        warn(f"{name}: no prescription label with a mechanism section (HTTP {r.status_code})"); continue
    j = r.json(); lab = j["results"][0]; save(f"openfda_{name}_rx.json", json.dumps(j, indent=1))
    ok(f"{name}: {j['meta']['results']['total']} Rx labels with mechanism. First: {lab.get('openfda',{}).get('brand_name',['?'])[0]}")
    out(f"        {' '.join(lab['mechanism_of_action'])[:300]}...")
out()
out("Notes: openFDA covers US labels only, so names like 'paracetamol' or German brands need mapping first (PubChem synonyms help). "
    "OTC labels (Drug Facts) use different sections than prescription labels, so chunking must handle both layouts.")

with open("report.md", "w") as f: f.write("\n".join(REPORT) + "\n")
print("\nSaved report.md and raw responses in ./raw/")
