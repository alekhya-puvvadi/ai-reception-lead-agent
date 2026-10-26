import json

from evaluation import run_eval
from tests.fakes import FakeClient, good_reply

CASES = run_eval.load_cases()
WRONG_INTENT = {"c02"}    # model returns the wrong intent
BAD_JSON = {"c03"}        # model returns prose instead of JSON on every attempt


def oracle(transcript, call_no):
    case = next(c for c in CASES if c["transcript"] == transcript)
    if case["id"] in BAD_JSON:
        return "Sorry, I cannot do that."
    intent = "complaint" if case["id"] in WRONG_INTENT else case["expected_intent"]
    return good_reply(
        intent_type=intent, urgency=case["expected_urgency"],
        caller_name=case.get("expected_name"), callback_number=case.get("expected_phone"),
    )


def test_test_set_is_well_formed():
    assert len(CASES) == 25
    assert len({c["id"] for c in CASES}) == 25
    assert {c["category"] for c in CASES} == {"clear", "ambiguous", "multi_intent", "noisy", "accented"}


def test_summary_numbers_match_known_outcomes():
    results = run_eval.run(FakeClient(responder=oracle), CASES, "text", "v2", progress=lambda *_: None)
    summary = run_eval.summarize(results)
    assert summary["n_cases"] == 25
    assert summary["intent_accuracy"] == round(23 / 25, 4)    # one wrong intent, one failed case
    assert summary["pipeline_success_rate"] == round(24 / 25, 4)
    assert summary["error_types"] == {"invalid_json": 1}
    assert summary["invented_name_or_phone"] >= 0
    bad_ids = {r["id"] for r in run_eval.failures(results)}
    assert bad_ids == {"c02", "c03"}


def test_outputs_are_written(tmp_path):
    results = run_eval.run(FakeClient(responder=oracle), CASES[:5], "text", "v2", progress=lambda *_: None)
    summary = run_eval.summarize(results)
    meta = {"date": "2026-01-01", "mode": "text", "prompt": "v2", "chat_model": "m", "whisper_model": "w"}
    run_eval.write_outputs("demo", meta, summary, results, out_dir=tmp_path)
    for suffix in (".json", ".csv", "_errors.jsonl", "_report.md"):
        assert (tmp_path / f"demo{suffix}").exists()
    assert json.loads((tmp_path / "demo.json").read_text())["summary"]["n_cases"] == 5


def test_audio_mode_computes_wer(tmp_path):
    (tmp_path / "c01.wav").write_bytes(b"fake")
    reference = CASES[0]["transcript"]
    client = FakeClient(responder=oracle, transcript_text=reference)
    results = run_eval.run(client, CASES, "audio", "v2", audio_dir=tmp_path, progress=lambda *_: None)
    assert len(results) == 1                      # only cases with a recording are run
    assert results[0]["wer"] == 0
    assert results[0]["transcript_has_phone"] is True
    assert run_eval.summarize(results)["avg_wer"] == 0


def test_audio_mode_without_recordings_raises(tmp_path):
    import pytest
    from agent.llm import AgentError
    with pytest.raises(AgentError):
        run_eval.run(FakeClient(), CASES, "audio", "v2", audio_dir=tmp_path, progress=lambda *_: None)
