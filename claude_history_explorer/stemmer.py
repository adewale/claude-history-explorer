"""Pure-Python Porter stemmer.

An implementation of the Porter stemming algorithm (Porter, 1980) using only
the Python standard library. The algorithm reduces English words to their
stems through five steps of suffix-stripping rules conditioned on the
"measure" (roughly, syllable count) of the remaining stem.

Reference: https://tartarus.org/martin/PorterStemmer/def.txt

This module exposes a single function:

    stem(word: str) -> str

Example:
    >>> stem("running")
    'run'
    >>> stem("dependencies")
    'depend'
"""

import re


def _measure(stem: str) -> int:
    """Count consonant-vowel sequences (the 'measure' m) in a stem.

    The measure is the number of VC (vowel-consonant) pairs in the word,
    after mapping to a C/V pattern. For example:
        "tr"     -> CC       -> m=0
        "tree"   -> CCVV     -> m=0
        "trouble" -> CCVVCCVV -> m=1  (one VC pair after initial C's)
        "troubles" -> CCVVCCCVVC -> m=2

    Args:
        stem: The word stem to measure

    Returns:
        The measure m (non-negative integer)
    """
    # Map to consonant/vowel pattern
    cv = ""
    for i, ch in enumerate(stem):
        if ch in "aeiou":
            cv += "v"
        elif ch == "y" and i == 0:
            cv += "c"
        elif ch == "y" and i > 0 and stem[i - 1] in "aeiou":
            cv += "c"
        elif ch == "y":
            cv += "v"
        else:
            cv += "c"

    # Collapse runs
    collapsed = re.sub(r"c+", "C", cv)
    collapsed = re.sub(r"v+", "V", collapsed)

    # Strip leading C and trailing V
    collapsed = re.sub(r"^C", "", collapsed)
    collapsed = re.sub(r"V$", "", collapsed)

    # Count VC pairs
    return collapsed.count("VC")


def _has_vowel(stem: str) -> bool:
    """Check if stem contains a vowel (including y in vowel position)."""
    for i, ch in enumerate(stem):
        if ch in "aeiou":
            return True
        if ch == "y" and i > 0:
            return True
    return False


def _ends_double_consonant(stem: str) -> bool:
    """Check if stem ends with a double consonant (e.g., 'hopp', 'tann')."""
    if len(stem) < 2:
        return False
    return stem[-1] == stem[-2] and stem[-1] not in "aeiou"


def _ends_cvc(stem: str) -> bool:
    """Check if stem ends with consonant-vowel-consonant where last C is not w/x/y.

    This is the *o condition in the Porter algorithm.
    """
    if len(stem) < 3:
        return False

    def is_consonant(word: str, i: int) -> bool:
        ch = word[i]
        if ch in "aeiou":
            return False
        if ch == "y":
            return i == 0 or word[i - 1] in "aeiou"
        return True

    c1 = is_consonant(stem, len(stem) - 3)
    v = not is_consonant(stem, len(stem) - 2)
    c2 = is_consonant(stem, len(stem) - 1)

    if not (c1 and v and c2):
        return False

    # Last consonant must not be w, x, or y
    return stem[-1] not in "wxy"


def _step1a(word: str) -> str:
    """Step 1a: simple plural/possessive suffixes.

    SSES -> SS    caresses  -> caress
    IES  -> I     ponies    -> poni
    SS   -> SS    caress    -> caress
    S    ->       cats      -> cat
    """
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-2]
    if word.endswith("ss"):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _step1b(word: str) -> str:
    """Step 1b: -ed and -ing suffixes.

    (m>0) EED -> EE     agreed    -> agree
    (*v*) ED  ->        plastered -> plaster
    (*v*) ING ->        motoring  -> motor

    If the second or third rule is used, then:
      AT -> ATE      conflat(ed)  -> conflate
      BL -> BLE      troubl(ed)   -> trouble
      IZ -> IZE      siz(ed)      -> size
      (*d and not *L/*S/*Z) -> single letter
                     hopp(ing)    -> hop
      (m=1 and *o) -> E           fil(ing)     -> file
    """
    if word.endswith("eed"):
        stem = word[:-3]
        if _measure(stem) > 0:
            return word[:-1]  # EED -> EE
        return word

    modified = False
    if word.endswith("ed"):
        stem = word[:-2]
        if _has_vowel(stem):
            word = stem
            modified = True
    elif word.endswith("ing"):
        stem = word[:-3]
        if _has_vowel(stem):
            word = stem
            modified = True

    if modified:
        if word.endswith("at") or word.endswith("bl") or word.endswith("iz"):
            return word + "e"
        if _ends_double_consonant(word) and word[-1] not in "lsz":
            return word[:-1]
        if _measure(word) == 1 and _ends_cvc(word):
            return word + "e"

    return word


def _step1c(word: str) -> str:
    """Step 1c: turn terminal y to i when there is another vowel in the stem.

    (*v*) Y -> I    happy -> happi, sky -> sky
    """
    if word.endswith("y"):
        stem = word[:-1]
        if _has_vowel(stem):
            return stem + "i"
    return word


def _step2(word: str) -> str:
    """Step 2: map double suffixes to single ones.

    (m>0) ATIONAL -> ATE     relational   -> relate
    (m>0) TIONAL  -> TION    conditional  -> condition
    (m>0) ENCI    -> ENCE    valenci      -> valence
    (m>0) ANCI    -> ANCE    hesitanci    -> hesitance
    (m>0) IZER    -> IZE     customizer   -> customize
    (m>0) ABLI    -> ABLE    adjustabli   -> adjustable
    (m>0) ALLI    -> AL      radicalli    -> radical
    (m>0) ENTLI   -> ENT     differentli  -> different
    (m>0) ELI     -> E       vileli       -> vile
    (m>0) OUSLI   -> OUS     analogousli  -> analogous
    (m>0) IZATION -> IZE     vietnamization -> vietnamize
    (m>0) ATION   -> ATE     predication  -> predicate
    (m>0) ATOR    -> ATE     operator     -> operate
    (m>0) ALISM   -> AL      feudalism    -> feudal
    (m>0) IVENESS -> IVE     decisiveness -> decisive
    (m>0) FULNESS -> FUL     hopefulness  -> hopeful
    (m>0) OUSNES  -> OUS     callousness  -> callous
    (m>0) ALITI   -> AL      formaliti    -> formal
    (m>0) IVITI   -> IVE     sensitiviti  -> sensitive
    (m>0) BILITI  -> BLE     sensibiliti  -> sensible
    """
    pairs = [
        ("ational", "ate"),
        ("tional", "tion"),
        ("enci", "ence"),
        ("anci", "ance"),
        ("izer", "ize"),
        ("abli", "able"),
        ("alli", "al"),
        ("entli", "ent"),
        ("eli", "e"),
        ("ousli", "ous"),
        ("ization", "ize"),
        ("ation", "ate"),
        ("ator", "ate"),
        ("alism", "al"),
        ("iveness", "ive"),
        ("fulness", "ful"),
        ("ousness", "ous"),
        ("aliti", "al"),
        ("iviti", "ive"),
        ("biliti", "ble"),
    ]
    for suffix, replacement in pairs:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if _measure(stem) > 0:
                return stem + replacement
            return word
    return word


def _step3(word: str) -> str:
    """Step 3: further suffix removal.

    (m>0) ICATE -> IC    triplicate -> triplic
    (m>0) ATIVE ->       formative  -> form
    (m>0) ALIZE -> AL    formalize  -> formal
    (m>0) ICITI -> IC    electriciti -> electric
    (m>0) ICAL  -> IC    electrical -> electric
    (m>0) FUL   ->       hopeful    -> hope
    (m>0) NESS  ->       goodness   -> good
    """
    pairs = [
        ("icate", "ic"),
        ("ative", ""),
        ("alize", "al"),
        ("iciti", "ic"),
        ("ical", "ic"),
        ("ful", ""),
        ("ness", ""),
    ]
    for suffix, replacement in pairs:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if _measure(stem) > 0:
                return stem + replacement
            return word
    return word


def _step4(word: str) -> str:
    """Step 4: remove final suffixes.

    (m>1) AL, ANCE, ENCE, ER, IC, ABLE, IBLE, ANT, EMENT, MENT, ENT,
          ION (where S or T precedes), OU, ISM, ATE, ITI, OUS, IVE, IZE
    """
    suffixes = [
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant",
        "ement", "ment", "ent", "ion", "ou", "ism", "ate", "iti",
        "ous", "ive", "ize",
    ]
    for suffix in suffixes:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if suffix == "ion":
                # ION requires preceding S or T
                if _measure(stem) > 1 and stem and stem[-1] in "st":
                    return stem
            else:
                if _measure(stem) > 1:
                    return stem
            return word
    return word


def _step5a(word: str) -> str:
    """Step 5a: remove final E.

    (m>1)       E ->      probate -> probat
    (m=1 and not *o) E -> rate -> rate (no change because *o)
    """
    if word.endswith("e"):
        stem = word[:-1]
        if _measure(stem) > 1:
            return stem
        if _measure(stem) == 1 and not _ends_cvc(stem):
            return stem
    return word


def _step5b(word: str) -> str:
    """Step 5b: remove double L.

    (m>1 and *d and *L) -> single letter
    e.g., controll -> control, roll -> roll
    """
    if word.endswith("ll") and _measure(word) > 1:
        return word[:-1]
    return word


def stem(word: str) -> str:
    """Apply the Porter stemming algorithm to a single word.

    The algorithm applies five steps of suffix-stripping rules. Each step
    is conditioned on the "measure" of the remaining stem to avoid
    over-stemming short words.

    Args:
        word: A single lowercase English word. Non-alphabetic characters
              and uppercase letters produce undefined results.

    Returns:
        The stemmed form of the word.

    Examples:
        >>> stem("running")
        'run'
        >>> stem("dependencies")
        'depend'
        >>> stem("caresses")
        'caress'
        >>> stem("ponies")
        'poni'
    """
    if len(word) <= 2:
        return word

    word = _step1a(word)
    word = _step1b(word)
    word = _step1c(word)
    word = _step2(word)
    word = _step3(word)
    word = _step4(word)
    word = _step5a(word)
    word = _step5b(word)

    return word
