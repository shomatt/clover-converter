from clover_midi.chord_detect import detect_chord, detect_chord_sym


def test_basic_triads():
    assert detect_chord([60, 64, 67]) == ("C", "none", "none", "none")     # C
    assert detect_chord([60, 63, 67]) == ("C", "m", "none", "none")        # Cm
    assert detect_chord([60, 64, 68]) == ("C", "aug", "none", "none")      # Caug
    assert detect_chord([60, 65, 67]) == ("C", "sus4", "none", "none")     # Csus4


def test_sevenths():
    assert detect_chord([60, 64, 67, 71]) == ("C", "maj7", "none", "none")  # Cmaj7
    assert detect_chord([60, 63, 67, 70]) == ("C", "m7", "none", "none")    # Cm7
    assert detect_chord([60, 64, 67, 70]) == ("C", "7", "none", "none")     # C7
    assert detect_chord([60, 63, 66, 70]) == ("C", "m7-5", "none", "none")  # Cm7b5
    assert detect_chord([60, 63, 66, 69]) == ("C", "dim7", "none", "none")  # Cdim7
    assert detect_chord([60, 63, 67, 71]) == ("C", "mmaj7", "none", "none")  # CmM7


def test_sixths():
    assert detect_chord([60, 64, 67, 69]) == ("C", "6", "none", "none")    # C6
    assert detect_chord([60, 63, 67, 69]) == ("C", "m6", "none", "none")   # Cm6


def test_slash_chord():
    # C major over G bass → C/G
    assert detect_chord([55, 60, 64, 67]) == ("C", "none", "none", "G")


def test_tensions():
    # Cmaj7 add 9 (D)
    assert detect_chord([60, 64, 67, 71, 74]) == ("C", "maj7", "9", "none")
    # C major add9 (no 7th)
    assert detect_chord([60, 64, 67, 74]) == ("C", "none", "add9", "none")


def test_detect_chord_sym():
    sym = detect_chord_sym([60, 64, 67, 71])   # Cmaj7
    assert sym.root == "C" and sym.kind == "major-seventh"


def test_empty():
    assert detect_chord([]) is None
