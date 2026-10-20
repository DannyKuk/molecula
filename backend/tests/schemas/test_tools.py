from molecula.schemas.tools import References


def test_a_passage_found_again_keeps_its_first_number() -> None:
    references = References()

    refs = [references.ref_of(chunk_id) for chunk_id in ["a", "b", "a", "c"]]

    assert refs == [1, 2, 1, 3]
