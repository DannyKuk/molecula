import re

from molecula.schemas.guard import Language

WORD = re.compile(r"[a-zäöüß]+")
GERMAN_LETTERS = re.compile(r"[äöüß]")


def words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Short words that say which language a message is in. Words that are common in both, such as
# "in", "was", "die", "will", "also", "man", "am" and "kind", are in neither list.
GERMAN_WORDS = words(
    """
    der das den dem des ein eine einen einem einer eines und oder aber doch denn dass weil wenn
    ob als ich du er es sie wir ihr mich mir dich dir ihm ihn uns euch sich mein meine meinen
    meinem meiner meines dein deine deinen deinem deiner sein seine seinen seinem seiner ihre
    ihren ihrem ihrer unser unsere unseren unserem unserer ist sind bin bist hat habe hab hast
    haben hatte wird werden wurde kann kannst können muss musst müssen soll sollte sollst darf
    dürfen möchte nicht kein keine keinen keinem keiner mit von zu zum zur bei beim für auf aus
    nach vor über unter ohne gegen durch seit statt vom im ins wie wo wer wen wem wann warum
    wieso weshalb wofür woher welche welcher welches welchen viel viele wieviel wieviele auch
    noch schon nur sehr jetzt heute heut gestern mal ja nein bitte danke gibt gibts geht gehts
    macht ne nen ner grad gerade eigentlich etwas alles hier da dann
    """
)
ENGLISH_WORDS = words(
    """
    the a and or but because if than then i you he she we they me him us them my your his her
    our their its it this that these those there here is are be been being were has have had
    do does did doing can could should would may might must not no of to for on at by with
    from about into what which who whom whose when where why how much many more most too very
    just only some any please thanks thank get take took taking give tell show
    """
)


def detect_language(text: str) -> Language:
    """German when the text has more German signals (German words, or words with ä, ö, ü or ß)
    than English words; English otherwise, so a tie, a bare drug name or another language
    gets English."""
    tokens = WORD.findall(text.lower())
    german = sum(word in GERMAN_WORDS or bool(GERMAN_LETTERS.search(word)) for word in tokens)
    english = sum(word in ENGLISH_WORDS for word in tokens)
    return "de" if german > english else "en"
