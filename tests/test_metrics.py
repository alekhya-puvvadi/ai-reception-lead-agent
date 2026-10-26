from evaluation import metrics


def test_wer_identical_is_zero():
    assert metrics.wer("call me today", "call me today") == 0


def test_wer_counts_substitution_and_deletion():
    assert metrics.wer("call me today please", "call he today") == 0.5


def test_wer_empty_reference():
    assert metrics.wer("", "") == 0.0
    assert metrics.wer("", "word") == 1.0


def test_name_match_uses_first_name():
    assert metrics.name_match("Rahul Sharma", "rahul")
    assert not metrics.name_match("Rahul Sharma", "Rohit")
    assert metrics.name_match(None, None)
    assert not metrics.name_match(None, "Invented Name")


def test_phone_match_ignores_formatting():
    assert metrics.phone_match("9876501234", "98765 01234")
    assert not metrics.phone_match("9876501234", "nine eight seven")
    assert not metrics.phone_match(None, "9876501234")


def test_spoken_digits_in_transcript():
    text = "call nine eight seven six five four three two one zero"
    assert metrics.transcript_has_phone("9876543210", text)
    assert not metrics.transcript_has_phone("9876543211", text)
