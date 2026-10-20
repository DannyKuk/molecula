import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
lines = []
n = 1
def atom(rec, name, resn, chain, resi, xyz, el):
    global n
    nm = name if len(name) == 4 else " " + name.ljust(3)
    lines.append(f"{rec:<6}{n:>5} {nm} {resn:>3} {chain}{resi:>4}    {xyz[0]:>8.3f}{xyz[1]:>8.3f}{xyz[2]:>8.3f}  1.00  0.00          {el:>2}")
    n += 1
for a in d["ligand"]["atoms"]:
    atom("HETATM", a["name"], d["ligand"]["code"][:3], "L", 600, a["xyz"], a["element"])
for r in d["pocket"]:
    for a in r["atoms"]:
        atom("ATOM", a["name"], r["name"], "A", r["number"], a["xyz"], a["element"])
trace = [{"xyz": t["xyz"], "sse": t["sse"], "chain": t["chain"]} for t in d["trace"]]
lig = d["ligand"]["atoms"]
pocket = {(r["number"]): r for r in d["pocket"]}
hb = []
for c in d["contacts"]:
    if c["kind"] != "hbond": continue
    r = pocket.get(c["residue"]["number"])
    if not r: continue
    ra = next((a for a in r["atoms"] if a["name"] == c["residue_atom"]), None)
    if ra: hb.append({"from": lig[c["ligand_atom"]]["xyz"], "to": ra["xyz"], "label": f'{c["residue"]["name"].title()}{c["residue"]["number"]}', "d": c["distance"]})
out = {"pdb": "\n".join(lines) + "\nEND\n", "trace": trace, "hbonds": hb}
name = sys.argv[2] if len(sys.argv) > 2 else None
if name:
    open(f"complex-{name}.js", "w", encoding="utf-8").write(f"window.COMPLEXES = window.COMPLEXES || {{}}; COMPLEXES.{name} = " + json.dumps(out) + ";\n")
else:
    open("complex-data.js", "w", encoding="utf-8").write("window.COMPLEX = " + json.dumps(out) + ";\n")
print(len(lines), len(hb))
