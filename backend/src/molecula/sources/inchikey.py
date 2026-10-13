CONNECTIVITY_BLOCK_LENGTH = 14


def connectivity_block(inchikey: str) -> str:
    """The InChIKey's first 14 characters: a hash of the connectivity, without stereo."""
    return inchikey[:CONNECTIVITY_BLOCK_LENGTH]
