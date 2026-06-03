"""
Second Brain — Transcript Processor
====================================
Entry point. Discovers transcript files, processes them through Claude,
and writes structured markdown notes into the Obsidian vault.

Usage:
    python process.py                  # Process all new files
    python process.py --dry-run        # Preview what would be processed
    python process.py --force          # Reprocess already-processed files
    python process.py --file path.txt  # Process a single specific file
    python process.py -v               # Verbose output
"""

import argparse
import sys
from pathlib import Path

from src.config import load_config
from src.discovery import discover_transcripts
from src.processor import process_transcript
from src.tracker import Tracker
from src.writer import write_note


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process transcripts into structured Obsidian notes"
    )
    parser.add_argument(
        "--force", action="store_true", help="Reprocess already-processed files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed without doing it"
    )
    parser.add_argument(
        "--file", type=str, metavar="PATH", help="Process a single specific file"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # --- Load configuration ---
    try:
        config = load_config()
    except (FileNotFoundError, EnvironmentError) as e:
        print(f"Config error: {e}")
        sys.exit(1)

    tracker = Tracker(config.tracking_file)

    # --- Discover files to process ---
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        candidates = [path]
    else:
        candidates = discover_transcripts(config.input_dir, config.supported_extensions)

    if not candidates:
        print(f"No transcript files found in: {config.input_dir}")
        return

    # --- Filter out already-processed files ---
    to_process = []
    for f in candidates:
        if not args.force and tracker.is_processed(f):
            if args.verbose:
                print(f"  Skip (already processed): {f.name}")
            continue
        to_process.append(f)

    if not to_process:
        print(
            f"All {len(candidates)} file(s) already processed. "
            "Use --force to reprocess."
        )
        return

    print(f"Processing {len(to_process)} file(s)...")

    if args.dry_run:
        for f in to_process:
            print(f"  Would process: {f.name}")
        return

    # --- Process each file ---
    success, failed = 0, 0
    for f in to_process:
        print(f"  {f.name} ... ", end="", flush=True)
        try:
            note_content = process_transcript(f, config)
            output_path = write_note(note_content, f, config)
            print(f"OK -> {output_path.name}")
            tracker.mark_processed(f, output_path)
            success += 1
        except Exception as e:
            print(f"FAILED")
            print(f"    Error: {e}")
            failed += 1

    # --- Summary ---
    print(f"\nDone. {success} processed", end="")
    if failed:
        print(f", {failed} failed.")
        sys.exit(1)
    else:
        print(".")


if __name__ == "__main__":
    main()
