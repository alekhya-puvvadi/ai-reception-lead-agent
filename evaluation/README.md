# Evaluation

This folder measures how well the pipeline understands calls. It uses a labelled test set,
reports accuracy per stage, and keeps the failures so they can be studied.

## Test set

`test_set.json` holds 25 scripted calls. Each has a transcript and ground-truth labels for
intent and urgency, plus the caller's name and phone number where the call contains them.

| Category | Cases | What it tests |
|---|---|---|
| clear | 8 | Direct, well-formed calls |
| ambiguous | 6 | Little or conflicting information, no stated purpose |
| multi_intent | 3 | Several questions in one call |
| noisy | 4 | Fillers, broken grammar, recognition-style spelling errors, digits spoken as words |
| accented | 4 | English mixed with Hindi, Kannada or Tamil, written in Roman script |

The transcripts are scripted by the author, not recorded from real callers. The noisy and accented
cases imitate how those calls look after transcription. To test real acoustic noise and accents,
record the calls (see "Audio mode").

## Labelling guide

Labels follow fixed rules so that ambiguous calls have one defensible answer.

**Intent** is the caller's primary purpose. When there are several, it is the one tied to what the
caller asks the institute to do.

- `admission`: says they want to join or enrol, even tentatively
- `fee_inquiry`: asks about price or payment without saying they want to join
- `placement_inquiry`: asks about jobs or placement support without saying they want to join
- `scheme_eligibility`: asks about government schemes, scholarships or subsidies
- `complaint`: reports a problem with the service, trainer, classes, payment or response
- `general_query`: asks for information about courses without saying they want to join
- `other`: no clear purpose, or unrelated to the institute

**Urgency**

- `High`: asks for action today or within a day, gives a near deadline, or reports an ongoing problem
- `Medium`: asks for a callback or details but gives no deadline
- `Low`: only browsing and does not ask for follow-up

**Name and phone**: expected only when the caller states them. When none is expected, the pipeline
must not return one, and every invented value is counted.

## Metrics

| Metric | Meaning |
|---|---|
| Intent accuracy, urgency accuracy | Share of all cases where the stored value equals the label. A case with no usable record counts as wrong |
| Name / phone extraction accuracy | Share of cases that contain the field where it was extracted correctly (first name; digits only) |
| Invented name or phone | Cases with no name or number where the pipeline returned one anyway |
| Valid JSON on first attempt | The first model reply parsed as JSON, before any retry |
| Valid schema on first attempt | The first reply also had every key and only allowed values |
| Pipeline success | A usable record was returned in the end, after retries |
| Word error rate (audio mode) | Whisper transcript against the reference transcript |
| Name / phone present in transcript (audio mode) | Whether speech-to-text kept the name and the digits intact |

## Running it

```bash
python -m evaluation.run_eval --prompt v1     # baseline prompt
python -m evaluation.run_eval --prompt v2     # refined prompt
python -m evaluation.compare text-v1 text-v2  # side-by-side table
```

`--delay` sets the pause between API calls (default 2 seconds) to stay inside free-tier rate limits.

Each run writes to `results/`, named `<mode>-<prompt>`:

- `*_report.md`: summary tables and every failed case
- `*.json`: full per-case results, including raw model output
- `*.csv`: one row per case, ready to open in Google Sheets or Excel
- `*_errors.jsonl`: failed cases with the raw output, for the error log

### Prompt versions

`v1` is the original baseline: plain instructions, no JSON mode, no retry, no validation.
`v2` adds labelling rules, JSON mode, tolerant parsing, one retry and normalisation of the output.
Comparing them shows what the prompt and the error handling each contribute.

## Audio mode

Audio mode transcribes real recordings first, so it also measures speech-to-text errors.

1. Record yourself reading a case's transcript aloud, including a few in a noisy room or with an
   accent you want to test.
2. Save the file in `audio/`, named after the case id: `c01.m4a`, `c02.wav`, and so on.
3. Run `python -m evaluation.run_eval --audio`.

Only cases that have a recording are run. Recordings must contain scripted test calls only, never
real callers.

## Limits of this evaluation

- 25 cases is small. A difference of one or two cases moves accuracy by 4 to 8 points, so treat
  small gaps as noise.
- The labels were written by one person.
- The test set tells you about these 25 calls, not about real call traffic.
- Lead score is not evaluated for accuracy. It is a subjective judgement with no ground truth.
