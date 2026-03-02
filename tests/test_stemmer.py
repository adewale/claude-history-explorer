"""Comprehensive tests for the pure-Python Porter stemmer.

Tests are organised in three layers:
1. Step-by-step unit tests (one test class per algorithm step)
2. End-to-end regression tests (known word→stem pairs from the reference)
3. Property-based tests (invariants that must hold for any input)

Reference: https://tartarus.org/martin/PorterStemmer/def.txt
"""

import string

import pytest

from claude_history_explorer.stemmer import (
    _ends_cvc,
    _ends_double_consonant,
    _has_vowel,
    _measure,
    _step1a,
    _step1b,
    _step1c,
    _step2,
    _step3,
    _step4,
    _step5a,
    _step5b,
    stem,
)


# =============================================================================
# Helper function tests
# =============================================================================


class TestMeasure:
    """Test the consonant-vowel measure (m) computation."""

    def test_empty(self):
        assert _measure("") == 0

    def test_single_consonant(self):
        assert _measure("t") == 0

    def test_single_vowel(self):
        assert _measure("a") == 0

    def test_cc(self):
        # "tr" → CC → m=0
        assert _measure("tr") == 0

    def test_ccvv(self):
        # "tree" → CCVV → m=0 (no VC pair after stripping)
        assert _measure("tree") == 0

    def test_trouble(self):
        # "trouble" → CCVVCCCV → m=1
        assert _measure("trouble") == 1

    def test_troubles(self):
        # "troubles" → CCVVCCVVC → m=2
        assert _measure("troubles") == 2

    def test_oat(self):
        # "oat" → VVC → m=1
        assert _measure("oat") == 1

    def test_private(self):
        # "private" → CCVVCVCV → m=2
        assert _measure("privat") == 2

    def test_y_as_consonant_at_start(self):
        # "yes" → y(C) e(V) s(C) → CVC → strip leading C → VC → m=1
        assert _measure("yes") == 1

    def test_y_as_vowel_after_consonant(self):
        # "y" after consonant is vowel
        assert _measure("by") == 0  # CV → m=0

    def test_crepuscul(self):
        # Longer word to verify m > 2
        assert _measure("crepuscul") >= 2


class TestHasVowel:
    """Test vowel detection including y-as-vowel."""

    def test_empty(self):
        assert not _has_vowel("")

    def test_consonants_only(self):
        assert not _has_vowel("bcdfg")

    def test_with_a(self):
        assert _has_vowel("cat")

    def test_with_e(self):
        assert _has_vowel("bed")

    def test_with_y_at_start(self):
        # y at start is consonant, not vowel
        assert not _has_vowel("y")

    def test_with_y_after_consonant(self):
        # y after consonant is vowel
        assert _has_vowel("by")

    def test_with_y_after_vowel(self):
        # y after vowel is consonant — but there's already a vowel (a)
        assert _has_vowel("ay")


class TestEndsDoubleConsonant:
    """Test the double consonant ending check."""

    def test_hopp(self):
        assert _ends_double_consonant("hopp")

    def test_tann(self):
        assert _ends_double_consonant("tann")

    def test_fall(self):
        assert _ends_double_consonant("fall")

    def test_miss(self):
        assert _ends_double_consonant("miss")

    def test_fizz(self):
        assert _ends_double_consonant("fizz")

    def test_not_double(self):
        assert not _ends_double_consonant("hop")

    def test_double_vowel(self):
        # "ee" — not consonants
        assert not _ends_double_consonant("tree")

    def test_short(self):
        assert not _ends_double_consonant("a")

    def test_empty(self):
        assert not _ends_double_consonant("")


class TestEndsCVC:
    """Test the consonant-vowel-consonant ending check (*o condition)."""

    def test_wil(self):
        assert _ends_cvc("wil")

    def test_hop(self):
        assert _ends_cvc("hop")

    def test_ends_w(self):
        # w is excluded
        assert not _ends_cvc("pow")

    def test_ends_x(self):
        # x is excluded
        assert not _ends_cvc("box")

    def test_ends_y(self):
        # y is excluded
        assert not _ends_cvc("toy")

    def test_too_short(self):
        assert not _ends_cvc("ab")

    def test_not_cvc(self):
        # "ool" → VVC, not CVC
        assert not _ends_cvc("ool")


# =============================================================================
# Step-by-step tests
# =============================================================================


class TestStep1a:
    """Step 1a: simple plural/possessive suffixes."""

    def test_sses(self):
        assert _step1a("caresses") == "caress"

    def test_ies(self):
        assert _step1a("ponies") == "poni"

    def test_ss(self):
        # SS → SS (no change)
        assert _step1a("caress") == "caress"

    def test_s(self):
        assert _step1a("cats") == "cat"

    def test_no_suffix(self):
        assert _step1a("run") == "run"


class TestStep1b:
    """Step 1b: -ed and -ing suffixes."""

    def test_eed_with_measure(self):
        # (m>0) EED → EE
        assert _step1b("agreed") == "agree"

    def test_eed_without_measure(self):
        # m=0 for "f" — no change
        assert _step1b("feed") == "feed"

    def test_ed_with_vowel(self):
        assert _step1b("plastered") == "plaster"

    def test_ed_without_vowel(self):
        # "shd" has no vowel — no change to "shed"
        assert _step1b("shed") == "shed"

    def test_ing_with_vowel(self):
        assert _step1b("motoring") == "motor"

    def test_ing_at_to_ate(self):
        assert _step1b("conflating") == "conflate"

    def test_ing_bl_to_ble(self):
        assert _step1b("troubling") == "trouble"

    def test_ing_iz_to_ize(self):
        assert _step1b("sizing") == "size"

    def test_ing_double_consonant_removed(self):
        assert _step1b("hopping") == "hop"

    def test_ing_double_consonant_lsz_kept(self):
        # double l/s/z are kept
        assert _step1b("falling") == "fall"
        assert _step1b("hissing") == "hiss"
        assert _step1b("fizzing") == "fizz"

    def test_ing_cvc_add_e(self):
        # m=1 and *o → add E
        assert _step1b("filing") == "file"

    def test_no_suffix(self):
        assert _step1b("run") == "run"


class TestStep1c:
    """Step 1c: terminal y→i."""

    def test_happy(self):
        assert _step1c("happi") == "happi"  # already i from step1a

    def test_sky(self):
        # "sk" has no vowel → no change
        assert _step1c("sky") == "sky"

    def test_enjoy_to_enjoi(self):
        # "enjo" has vowel → y→i
        assert _step1c("enjoy") == "enjoi"

    def test_no_y(self):
        assert _step1c("run") == "run"


class TestStep2:
    """Step 2: map double suffixes to single ones."""

    def test_relational(self):
        assert _step2("relational") == "relate"

    def test_conditional(self):
        assert _step2("conditional") == "condition"

    def test_enci(self):
        assert _step2("valenci") == "valence"

    def test_anci(self):
        assert _step2("hesitanci") == "hesitance"

    def test_izer(self):
        assert _step2("customizer") == "customize"

    def test_abli(self):
        assert _step2("adjustabli") == "adjustable"

    def test_alli(self):
        assert _step2("radicalli") == "radical"

    def test_entli(self):
        assert _step2("differentli") == "different"

    def test_eli(self):
        assert _step2("vileli") == "vile"

    def test_ousli(self):
        assert _step2("analogousli") == "analogous"

    def test_ization(self):
        assert _step2("vietnamization") == "vietnamize"

    def test_ation(self):
        assert _step2("predication") == "predicate"

    def test_ator(self):
        assert _step2("operator") == "operate"

    def test_alism(self):
        assert _step2("feudalism") == "feudal"

    def test_iveness(self):
        assert _step2("decisiveness") == "decisive"

    def test_fulness(self):
        assert _step2("hopefulness") == "hopeful"

    def test_ousness(self):
        assert _step2("callousness") == "callous"

    def test_aliti(self):
        assert _step2("formaliti") == "formal"

    def test_iviti(self):
        assert _step2("sensitiviti") == "sensitive"

    def test_biliti(self):
        assert _step2("sensibiliti") == "sensible"

    def test_m_zero_no_change(self):
        # If m=0, the rule doesn't fire
        assert _step2("ational") == "ational"


class TestStep3:
    """Step 3: further suffix removal."""

    def test_icate(self):
        assert _step3("triplicate") == "triplic"

    def test_ative(self):
        assert _step3("formative") == "form"

    def test_alize(self):
        assert _step3("formalize") == "formal"

    def test_iciti(self):
        assert _step3("electriciti") == "electric"

    def test_ical(self):
        assert _step3("electrical") == "electric"

    def test_ful(self):
        assert _step3("hopeful") == "hope"

    def test_ness(self):
        assert _step3("goodness") == "good"


class TestStep4:
    """Step 4: remove final suffixes (m>1)."""

    def test_al(self):
        assert _step4("revival") == "reviv"

    def test_ance(self):
        assert _step4("allowance") == "allow"

    def test_ence(self):
        assert _step4("inference") == "infer"

    def test_er(self):
        assert _step4("airliner") == "airlin"

    def test_ic(self):
        assert _step4("gyroscopic") == "gyroscop"

    def test_able(self):
        assert _step4("adjustable") == "adjust"

    def test_ible(self):
        assert _step4("defensible") == "defens"

    def test_ant(self):
        assert _step4("irritant") == "irrit"

    def test_ement(self):
        assert _step4("replacement") == "replac"

    def test_ment(self):
        assert _step4("adjustment") == "adjust"

    def test_ent(self):
        assert _step4("dependent") == "depend"

    def test_ion_with_s(self):
        assert _step4("adoption") == "adopt"

    def test_ion_with_t(self):
        # step4 in isolation: "activation" → remove "ion" (preceded by t) → "activat"
        # (the full pipeline goes activation→step2→activate→step4→activ)
        assert _step4("activation") == "activat"

    def test_ion_without_s_or_t(self):
        # "ion" without preceding s/t — no change
        assert _step4("criterion") == "criterion"

    def test_ou(self):
        assert _step4("homologou") == "homolog"

    def test_ism(self):
        assert _step4("communism") == "commun"

    def test_ate(self):
        assert _step4("activate") == "activ"

    def test_iti(self):
        assert _step4("angulariti") == "angular"

    def test_ous(self):
        assert _step4("homologous") == "homolog"

    def test_ive(self):
        assert _step4("effective") == "effect"

    def test_ize(self):
        assert _step4("bowdlerize") == "bowdler"


class TestStep5a:
    """Step 5a: remove final E."""

    def test_probate(self):
        assert _step5a("probate") == "probat"

    def test_rate(self):
        # m=1 and *o (ends CVC with t, not w/x/y) → keep E
        assert _step5a("rate") == "rate"

    def test_cease(self):
        assert _step5a("cease") == "ceas"


class TestStep5b:
    """Step 5b: remove double L."""

    def test_controll(self):
        assert _step5b("controll") == "control"

    def test_roll(self):
        # m=1 for "roll" — not > 1, so no change
        assert _step5b("roll") == "roll"


# =============================================================================
# End-to-end regression tests
# =============================================================================


class TestStemEndToEnd:
    """Full pipeline tests with known word→stem pairs.

    These are drawn from the Porter stemmer reference output and verified
    against multiple implementations.
    """

    # (input, expected_stem) — from the reference
    REFERENCE_PAIRS = [
        # Step 1 examples
        ("caresses", "caress"),
        ("ponies", "poni"),
        ("ties", "ti"),
        ("caress", "caress"),
        ("cats", "cat"),
        # Step 1b examples
        ("agreed", "agre"),
        ("plastered", "plaster"),
        ("motoring", "motor"),
        ("singing", "sing"),
        # Step 1c
        ("happy", "happi"),
        ("sky", "sky"),
        # Common programming words
        ("running", "run"),
        ("tests", "test"),
        ("testing", "test"),
        ("fixing", "fix"),
        ("fixed", "fix"),
        ("deployment", "deploy"),
        ("deploying", "deploi"),  # step1c: y→i
        ("configuration", "configur"),
        ("dependencies", "depend"),
        ("dependency", "depend"),
        ("committing", "commit"),
        ("committed", "commit"),
        ("linting", "lint"),
        ("errors", "error"),
        ("failing", "fail"),
        ("failed", "fail"),
        ("building", "build"),
        ("checking", "check"),
        ("installing", "instal"),
        # Common English words
        ("generalizations", "gener"),
        ("oscillators", "oscil"),
        ("communism", "commun"),
        ("formalize", "formal"),
        ("triplicate", "triplic"),
        ("hopeful", "hope"),
        ("goodness", "good"),
        ("revival", "reviv"),
        ("allowance", "allow"),
        ("inference", "infer"),
        ("effective", "effect"),
    ]

    @pytest.mark.parametrize("word,expected", REFERENCE_PAIRS)
    def test_reference_pair(self, word, expected):
        assert stem(word) == expected

    def test_short_words_unchanged(self):
        """Words of 2 chars or less are returned as-is."""
        assert stem("a") == "a"
        assert stem("to") == "to"
        assert stem("me") == "me"
        assert stem("") == ""

    def test_already_stemmed(self):
        """Applying stem twice should be idempotent for most words."""
        words = ["run", "test", "fix", "build", "lint", "check"]
        for word in words:
            assert stem(word) == word


# =============================================================================
# Property-based tests (invariants)
# =============================================================================


class TestStemProperties:
    """Property-based tests: invariants that must hold for any input."""

    SAMPLE_WORDS = [
        "running",
        "tests",
        "caresses",
        "ponies",
        "agreed",
        "plastered",
        "motoring",
        "happy",
        "sky",
        "dependency",
        "configuration",
        "deployment",
        "generalization",
        "oscillator",
        "triplicate",
        "formalize",
        "effective",
        "communism",
        "hopeful",
        "goodness",
        "revival",
        "allowance",
        "inference",
        "activation",
        "replacement",
        "adjustable",
        "defensible",
        "different",
        "radical",
        "decisive",
        "analogous",
        "conditional",
        "relational",
        "sensible",
        "electrical",
        "bowdlerize",
        "homologous",
        "irritant",
        "dependent",
        "probate",
        "controll",
    ]

    def test_output_no_longer_than_input(self):
        """Stemming should never make a word longer (except rare e-insertion)."""
        # Some words get an 'e' added (conflat→conflate), but the final
        # stem should never be dramatically longer than the input
        for word in self.SAMPLE_WORDS:
            result = stem(word)
            # Allow up to 1 char longer (the e-insertion case)
            assert len(result) <= len(word) + 1, f"stem({word!r}) = {result!r}"

    def test_output_is_lowercase(self):
        """Stemmer expects lowercase input; output should remain lowercase."""
        for word in self.SAMPLE_WORDS:
            result = stem(word)
            assert result == result.lower(), f"stem({word!r}) = {result!r}"

    def test_output_is_alphabetic(self):
        """Output should be purely alphabetic (no digits, punctuation)."""
        for word in self.SAMPLE_WORDS:
            result = stem(word)
            assert result.isalpha(), f"stem({word!r}) = {result!r}"

    def test_output_is_nonempty(self):
        """Stem should never return empty for non-empty input."""
        for word in self.SAMPLE_WORDS:
            result = stem(word)
            assert len(result) > 0, f"stem({word!r}) is empty"

    def test_idempotence(self):
        """Applying stem twice should produce the same result as once.

        This is a weaker property — not guaranteed by Porter, but holds
        for the vast majority of words and is a good regression check.
        """
        # Some words won't be strictly idempotent (e.g., "probat" → "probat"),
        # but most should be
        idempotent_words = [
            "running", "tests", "fixing", "building", "checking",
            "deploy", "error", "lint", "commit",
        ]
        for word in idempotent_words:
            first = stem(word)
            second = stem(first)
            assert first == second, (
                f"Not idempotent: stem({word!r})={first!r}, "
                f"stem({first!r})={second!r}"
            )

    def test_same_stem_for_morphological_variants(self):
        """Words that share a root should produce the same stem."""
        groups = [
            ["run", "running", "runs"],
            ["test", "tests", "testing"],
            ["fix", "fixed", "fixing", "fixes"],
            ["build", "building", "builds"],
            # "deployment"→"deploy" diverges from "deploy"→"deploi" (step1c y→i).
            # The four -y forms all converge to "deploi".
            ["deploy", "deployed", "deploying", "deploys"],
            ["depend", "dependent", "dependency", "dependencies"],
            ["fail", "failed", "failing", "fails"],
            ["commit", "committed", "committing", "commits"],
            ["check", "checked", "checking", "checks"],
        ]
        for group in groups:
            stems = {stem(w) for w in group}
            assert len(stems) == 1, (
                f"Variants {group} produced different stems: "
                f"{', '.join(f'{w}→{stem(w)}' for w in group)}"
            )

    def test_different_roots_produce_different_stems(self):
        """Words with different meanings should not collide."""
        pairs = [
            ("run", "fix"),
            ("test", "build"),
            ("deploy", "lint"),
            ("commit", "error"),
        ]
        for a, b in pairs:
            assert stem(a) != stem(b), (
                f"Collision: stem({a!r}) == stem({b!r}) == {stem(a)!r}"
            )

    def test_pure_consonants(self):
        """Words with no vowels should survive without crashing."""
        result = stem("zzz")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_all_vowels(self):
        """Words with only vowels should survive without crashing."""
        result = stem("aeiou")
        assert isinstance(result, str)

    def test_single_characters(self):
        """Single characters should be returned as-is."""
        for ch in string.ascii_lowercase:
            assert stem(ch) == ch
