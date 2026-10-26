"""Command-line interface: analyse calls without the web UI.

    python cli.py audio call1.m4a call2.wav
    python cli.py text "Hi, I want to join the Python course. Call me today."
    python cli.py list --sort score
    python cli.py stats
"""

import argparse
from pathlib import Path

from agent import database as db
from agent.llm import AgentError, extract_lead, get_client, transcribe


def _analyse(client, transcript: str, source: str) -> None:
    record = extract_lead(client, transcript)
    call_id = db.insert_call(transcript, record, source=source)
    print(f"  Saved lead #{call_id}: {record['intent_type']} | {record['urgency']} urgency | score {record['lead_score']}")
    print(f"  {record['summary']}")
    print(f"  Suggested reply: {record['suggested_reply']}\n")


def _list(args) -> None:
    calls = db.fetch_calls(intents=[args.intent] if args.intent else None, order=args.sort)
    for c in calls:
        print(f"#{c['id']:<3} {c['lead_score']:>3}  {c['urgency']:<6} {c['intent_type']:<18} "
              f"{(c['caller_name'] or '-'):<14} {c['status']:<10} {c['summary']}")
    print(f"\n{len(calls)} call(s)")


def _stats(_args) -> None:
    stats = db.get_stats()
    print(f"Total calls: {stats['total']} | High priority: {stats['high_priority']} | "
          f"Average score: {stats['avg_score']} | Awaiting follow-up: {stats['awaiting_follow_up']}")
    for intent, count in stats["by_intent"].items():
        print(f"  {intent:<20} {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Reception & Lead Management Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audio = sub.add_parser("audio", help="transcribe and analyse audio files")
    p_audio.add_argument("files", nargs="+", type=Path)
    p_text = sub.add_parser("text", help="analyse a typed transcript")
    p_text.add_argument("transcript")
    p_list = sub.add_parser("list", help="list saved leads")
    p_list.add_argument("--sort", choices=["recent", "score"], default="recent")
    p_list.add_argument("--intent")
    sub.add_parser("stats", help="show summary numbers")

    args = parser.parse_args()
    db.init_db()
    try:
        if args.command == "audio":
            client = get_client()
            for path in args.files:
                print(f"{path.name}")
                _analyse(client, transcribe(client, path.read_bytes(), path.name), source="upload")
        elif args.command == "text":
            _analyse(get_client(), args.transcript, source="typed")
        elif args.command == "list":
            _list(args)
        else:
            _stats(args)
    except (AgentError, OSError) as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
