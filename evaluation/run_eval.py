"""Evaluate the pipeline against the labelled test set.

    python -m evaluation.run_eval                  # text mode, refined prompt (v2)
    python -m evaluation.run_eval --prompt v1      # baseline prompt, for before/after
    python -m evaluation.run_eval --audio          # end to end: audio -> Whisper -> LLM

Text mode feeds the reference transcripts straight to the LLM, so it measures understanding.
Audio mode transcribes recordings in evaluation/audio/ first (named c01.m4a, c02.wav, ...),
so it also measures speech-to-text errors. Only cases that have a recording are run.
"""

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent import config
from agent.llm import AgentError, active_models, extract_lead_detailed, get_client, transcribe
from agent.prompts import DEFAULT_PROMPT, PROMPTS

from . import metrics

EVAL_DIR = Path(__file__).resolve().parent
TEST_SET = EVAL_DIR / "test_set.json"
AUDIO_DIR = EVAL_DIR / "audio"
RESULTS_DIR = EVAL_DIR / "results"
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}


def load_cases(path: Path = TEST_SET) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_audio(case_id: str, audio_dir: Path = AUDIO_DIR) -> Optional[Path]:
    for path in sorted(Path(audio_dir).glob(f"{case_id}.*")):
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            return path
    return None


# ---------------------------------------------------------------- one case
def evaluate_case(client, case: dict, mode: str, prompt: str, audio_dir: Path = AUDIO_DIR) -> dict:
    out = {
        "id": case["id"], "category": case["category"],
        "expected_intent": case["expected_intent"], "expected_urgency": case["expected_urgency"],
        "expected_name": case.get("expected_name"), "expected_phone": case.get("expected_phone"),
        "reference_transcript": case["transcript"],
        "intent_correct": False, "urgency_correct": False,
        "name_correct": False, "phone_correct": False,
    }
    transcript = case["transcript"]

    if mode == "audio":
        path = find_audio(case["id"], audio_dir)
        out["audio_file"] = path.name
        started = time.perf_counter()
        try:
            transcript = transcribe(client, path.read_bytes(), path.name)
        except AgentError as exc:
            out.update(success=False, error=str(exc), error_type="transcription_error")
            return out
        out["transcription_latency_s"] = round(time.perf_counter() - started, 3)
        out["whisper_transcript"] = transcript
        out["wer"] = round(metrics.wer(case["transcript"], transcript), 4)
        if case.get("expected_name"):
            out["transcript_has_name"] = metrics.transcript_has_name(case["expected_name"], transcript)
        if case.get("expected_phone"):
            out["transcript_has_phone"] = metrics.transcript_has_phone(case["expected_phone"], transcript)

    result = extract_lead_detailed(client, transcript, prompt)
    out.update(
        success=result.record is not None,
        first_json_ok=result.first_json_ok, first_schema_ok=result.first_schema_ok,
        schema_problems=result.first_problems, attempts=result.attempts,
        latency_s=round(result.latency_s, 3), error=result.error, error_type=result.error_type,
        raw_output=result.raw_text,
    )

    record = result.record
    if record:
        out.update(
            pred_intent=record.get("intent_type"), pred_urgency=record.get("urgency"),
            pred_name=record.get("caller_name"), pred_phone=record.get("callback_number"),
            pred_score=record.get("lead_score"), pred_summary=record.get("summary"),
            intent_correct=record.get("intent_type") == case["expected_intent"],
            urgency_correct=record.get("urgency") == case["expected_urgency"],
            name_correct=metrics.name_match(case.get("expected_name"), record.get("caller_name")),
            phone_correct=metrics.phone_match(case.get("expected_phone"), str(record.get("callback_number") or "")),
        )
    return out


# ---------------------------------------------------------------- aggregate
def _round(value, digits=4):
    return None if value is None else round(value, digits)


def summarize(results: list[dict]) -> dict:
    n = len(results)
    with_name = [r for r in results if r["expected_name"]]
    with_phone = [r for r in results if r["expected_phone"]]
    without_name = [r for r in results if not r["expected_name"] and r.get("success")]
    without_phone = [r for r in results if not r["expected_phone"] and r.get("success")]

    summary = {
        "n_cases": n,
        "pipeline_success_rate": _round(metrics.rate(r["success"] for r in results)),
        "first_attempt_json_rate": _round(metrics.rate(r.get("first_json_ok", False) for r in results)),
        "first_attempt_schema_rate": _round(metrics.rate(r.get("first_schema_ok", False) for r in results)),
        "intent_accuracy": _round(metrics.rate(r["intent_correct"] for r in results)),
        "urgency_accuracy": _round(metrics.rate(r["urgency_correct"] for r in results)),
        "name_extraction_accuracy": _round(metrics.rate(r["name_correct"] for r in with_name)),
        "phone_extraction_accuracy": _round(metrics.rate(r["phone_correct"] for r in with_phone)),
        "invented_name_or_phone": sum(1 for r in without_name if not r["name_correct"])
        + sum(1 for r in without_phone if not r["phone_correct"]),
        "avg_latency_s": _round(sum(r.get("latency_s", 0) for r in results) / n if n else None, 3),
        "avg_attempts": _round(sum(r.get("attempts", 0) for r in results) / n if n else None, 2),
        "error_types": dict(Counter(r["error_type"] for r in results if r.get("error_type"))),
        "by_category": {},
    }

    for category in sorted({r["category"] for r in results}):
        subset = [r for r in results if r["category"] == category]
        summary["by_category"][category] = {
            "n": len(subset),
            "intent_accuracy": _round(metrics.rate(r["intent_correct"] for r in subset)),
            "urgency_accuracy": _round(metrics.rate(r["urgency_correct"] for r in subset)),
        }

    wers = [r["wer"] for r in results if "wer" in r]
    if wers:
        summary["avg_wer"] = _round(sum(wers) / len(wers))
        summary["transcript_name_rate"] = _round(
            metrics.rate(r["transcript_has_name"] for r in results if "transcript_has_name" in r))
        summary["transcript_phone_rate"] = _round(
            metrics.rate(r["transcript_has_phone"] for r in results if "transcript_has_phone" in r))
        summary["wer_by_category"] = {
            c: _round(sum(r["wer"] for r in results if r["category"] == c and "wer" in r)
                      / max(1, sum(1 for r in results if r["category"] == c and "wer" in r)))
            for c in sorted({r["category"] for r in results if "wer" in r})
        }
    return summary


# ---------------------------------------------------------------- outputs
def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def failures(results: list[dict]) -> list[dict]:
    return [r for r in results if not (r["success"] and r["intent_correct"] and r["urgency_correct"])]


def build_report(name: str, meta: dict, summary: dict, results: list[dict]) -> str:
    lines = [
        f"# Evaluation report: {name}", "",
        f"- Date: {meta['date']}",
        f"- Mode: {meta['mode']}  |  Prompt: {meta['prompt']}  |  Cases: {summary['n_cases']}",
        f"- Chat model: {meta['chat_model']}  |  Speech model: {meta['whisper_model']}", "",
        "## Results", "", "| Metric | Value |", "|---|---|",
        f"| Intent accuracy | {_pct(summary['intent_accuracy'])} |",
        f"| Urgency accuracy | {_pct(summary['urgency_accuracy'])} |",
        f"| Name extraction accuracy | {_pct(summary['name_extraction_accuracy'])} |",
        f"| Phone extraction accuracy | {_pct(summary['phone_extraction_accuracy'])} |",
        f"| Valid JSON on first attempt | {_pct(summary['first_attempt_json_rate'])} |",
        f"| Valid schema on first attempt | {_pct(summary['first_attempt_schema_rate'])} |",
        f"| Pipeline success (usable record returned) | {_pct(summary['pipeline_success_rate'])} |",
        f"| Invented name or phone (expected none) | {summary['invented_name_or_phone']} |",
        f"| Average latency | {summary['avg_latency_s']} s |",
    ]
    if "avg_wer" in summary:
        lines += [
            f"| Average word error rate (Whisper) | {_pct(summary['avg_wer'])} |",
            f"| Name present in Whisper transcript | {_pct(summary['transcript_name_rate'])} |",
            f"| Phone number correct in Whisper transcript | {_pct(summary['transcript_phone_rate'])} |",
        ]
    lines += ["", "## By category", "", "| Category | Cases | Intent | Urgency |", "|---|---|---|---|"]
    for cat, s in summary["by_category"].items():
        lines.append(f"| {cat} | {s['n']} | {_pct(s['intent_accuracy'])} | {_pct(s['urgency_accuracy'])} |")

    if summary.get("wer_by_category"):
        lines += ["", "## Word error rate by category", "", "| Category | WER |", "|---|---|"]
        lines += [f"| {c} | {_pct(v)} |" for c, v in summary["wer_by_category"].items()]

    if summary["error_types"]:
        lines += ["", "## Errors", ""] + [f"- {k}: {v}" for k, v in summary["error_types"].items()]

    bad = failures(results)
    lines += ["", f"## Cases that failed ({len(bad)} of {summary['n_cases']})", ""]
    if not bad:
        lines.append("None.")
    for r in bad:
        lines.append(f"**{r['id']}** ({r['category']}): intent expected `{r['expected_intent']}`, "
                     f"got `{r.get('pred_intent')}`; urgency expected `{r['expected_urgency']}`, "
                     f"got `{r.get('pred_urgency')}`" + (f"; error: {r['error']}" if r.get("error") else ""))
        lines.append(f"> {r['reference_transcript']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(name: str, meta: dict, summary: dict, results: list[dict], out_dir: Path = RESULTS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "cases": results}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    import csv
    columns = ["id", "category", "expected_intent", "pred_intent", "intent_correct",
               "expected_urgency", "pred_urgency", "urgency_correct", "expected_name", "pred_name",
               "name_correct", "expected_phone", "pred_phone", "phone_correct", "first_json_ok",
               "first_schema_ok", "attempts", "latency_s", "wer", "error_type", "error"]
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    with open(out_dir / f"{name}_errors.jsonl", "w", encoding="utf-8") as f:
        for r in failures(results):
            f.write(json.dumps({k: r.get(k) for k in (
                "id", "category", "reference_transcript", "expected_intent", "pred_intent",
                "expected_urgency", "pred_urgency", "error_type", "error", "schema_problems", "raw_output",
            )}, ensure_ascii=False) + "\n")

    (out_dir / f"{name}_report.md").write_text(build_report(name, meta, summary, results), encoding="utf-8")


# ---------------------------------------------------------------- run
def run(client, cases: list[dict], mode: str = "text", prompt: str = DEFAULT_PROMPT,
        delay: float = 0.0, audio_dir: Path = AUDIO_DIR, progress=print) -> list[dict]:
    if mode == "audio":
        cases = [c for c in cases if find_audio(c["id"], audio_dir)]
        if not cases:
            raise AgentError(f"No recordings found in {audio_dir}. Name files after case ids, e.g. c01.m4a.")
    results = []
    for i, case in enumerate(cases, start=1):
        result = evaluate_case(client, case, mode, prompt, audio_dir)
        results.append(result)
        flag = "ok" if result["success"] and result["intent_correct"] and result["urgency_correct"] else "check"
        progress(f"[{i}/{len(cases)}] {case['id']} {case['category']:<12} {flag}")
        if delay and i < len(cases):
            time.sleep(delay)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", choices=sorted(PROMPTS), default=DEFAULT_PROMPT)
    parser.add_argument("--audio", action="store_true", help="transcribe recordings first (end to end)")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between calls, to respect rate limits")
    parser.add_argument("--name", help="run name (default: <mode>-<prompt>)")
    args = parser.parse_args()

    mode = "audio" if args.audio else "text"
    name = args.name or f"{mode}-{args.prompt}"
    try:
        client = get_client()
        results = run(client, load_cases(), mode, args.prompt, args.delay)
    except AgentError as exc:
        raise SystemExit(f"Error: {exc}")

    meta = {"date": datetime.now().isoformat(timespec="seconds"), "mode": mode, "prompt": args.prompt,
            "chat_model": active_models()["chat"], "whisper_model": active_models()["speech"]}
    summary = summarize(results)
    write_outputs(name, meta, summary, results)
    print(f"\nIntent accuracy: {_pct(summary['intent_accuracy'])} | "
          f"Urgency accuracy: {_pct(summary['urgency_accuracy'])} | "
          f"Valid JSON first attempt: {_pct(summary['first_attempt_json_rate'])}")
    print(f"Wrote evaluation/results/{name}_report.md (and .json, .csv, _errors.jsonl)")


if __name__ == "__main__":
    main()
