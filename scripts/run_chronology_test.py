#!/usr/bin/env python3
"""
Feed a raw records file to a local Ollama model and ask it to build a cited chronology.
Usage: python3 run_chronology_test.py <records_file> [model_tag]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "chronology_prompt.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text()


def main():
    if len(sys.argv) < 2:
        print("Usage: run_chronology_test.py <records_file> [model_tag]")
        sys.exit(1)

    records_path = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "llama3.1:8b"

    with open(records_path) as f:
        records_text = f.read()

    prompt = PROMPT_TEMPLATE.format(records=records_text)

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})

    start = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.load(resp)
    wall_time = time.time() - start

    print("=" * 70)
    print(f"MODEL: {model}")
    print("=" * 70)
    print(data["response"])
    print("=" * 70)
    eval_count = data.get("eval_count", 0)
    eval_duration_s = data.get("eval_duration", 0) / 1e9
    print(f"wall time: {wall_time:.1f}s | output tokens: {eval_count} | "
          f"gen speed: {eval_count / eval_duration_s:.1f} tok/s" if eval_duration_s else "")


if __name__ == "__main__":
    main()
