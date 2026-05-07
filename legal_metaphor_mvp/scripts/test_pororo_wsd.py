"""Smoke test for optional PORORO Korean WSD."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wsd.pororo_wsd import PororoKoreanWSD  # noqa: E402


def main() -> int:
    examples = [
        "법질서의 통일성을 확보하기 위한 것이다.",
        "머리에 이가 있나봐.",
    ]
    try:
        analyzer = PororoKoreanWSD()
    except RuntimeError as exc:
        print(str(exc))
        print("해결 방법:")
        print("1. conda env create -f envs/pororo-wsd.yml")
        print("2. conda activate pororo-wsd")
        print("3. python scripts/test_pororo_wsd.py")
        return 1

    for text in examples:
        print(f"\n[입력] {text}")
        print(json.dumps(analyzer.analyze(text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
