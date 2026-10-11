from molecula.ingest.conformers import embed_conformer

# Ritonavir: a small molecule PubChem has no conformer for (18 rotatable bonds).
RITONAVIR = (
    "CC(C)C1=NC(=CS1)CN(C)C(=O)N[C@@H](C(C)C)C(=O)N[C@@H](CC2=CC=CC=C2)C[C@@H]"
    "([C@H](CC3=CC=CC=C3)NC(=O)OCC4=CN=CS4)O"
)


def test_embeds_a_3d_conformer_with_hydrogens() -> None:
    sdf = embed_conformer(392622, RITONAVIR)

    assert sdf is not None
    lines = sdf.splitlines()
    assert lines[0] == "392622"
    assert (lines[3][:3], lines[3][3:6]) == (" 98", "101")
    assert {line.split()[2] for line in lines[4:102]} != {"0.0000"}
    assert sdf.endswith("$$$$\n")


def test_is_reproducible() -> None:
    assert embed_conformer(392622, RITONAVIR) == embed_conformer(392622, RITONAVIR)


def test_unparsable_smiles_gives_none() -> None:
    assert embed_conformer(1, "C1CC(") is None
