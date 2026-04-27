import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from project_paths import DATASETS_FINAL_DIR, DATASETS_TEST_DIR, ensure_standard_directories


DEFAULT_SEED = 20260426
DEFAULT_SAMPLE_SIZES = {
    "JU": 20,
    "MC": 20,
    "MSR": 30,
    "SAR": 30,
    "SC": 20,
    "SQ": 20,
    "SSC": 30,
}


def load_questions(path: Path) -> list[dict]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            questions.append(json.loads(line))
    return questions


def detect_type_tag(path: Path, questions: list[dict]) -> str:
    if questions:
        question_id = questions[0].get("question_id", "")
        if "-" in question_id:
            return question_id.split("-", 1)[0]
    parts = path.stem.split("_")
    return parts[-1].upper() if parts else "UNK"


def round_robin_stratified_sample(questions: list[dict], sample_size: int, rng: random.Random) -> list[dict]:
    if len(questions) <= sample_size:
        return sorted(questions, key=lambda item: item.get("question_id", ""))

    by_difficulty: dict[str, list[dict]] = defaultdict(list)
    for item in questions:
        by_difficulty[(item.get("difficulty") or "unknown").lower()].append(item)

    groups = []
    for difficulty in sorted(by_difficulty.keys()):
        items = list(by_difficulty[difficulty])
        rng.shuffle(items)
        groups.append(items)

    selected = []
    seen_ids = set()
    while len(selected) < sample_size and any(groups):
        next_groups = []
        for items in groups:
            while items and items[0].get("question_id", "") in seen_ids:
                items.pop(0)
            if not items:
                continue
            candidate = items.pop(0)
            question_id = candidate.get("question_id", "")
            if question_id not in seen_ids:
                selected.append(candidate)
                seen_ids.add(question_id)
                if len(selected) >= sample_size:
                    break
            if items:
                next_groups.append(items)
        groups = next_groups

    if len(selected) < sample_size:
        remaining = [item for item in questions if item.get("question_id", "") not in seen_ids]
        rng.shuffle(remaining)
        selected.extend(remaining[: sample_size - len(selected)])

    return sorted(selected, key=lambda item: item.get("question_id", ""))


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def difficulty_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[(item.get("difficulty") or "unknown").lower()] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    ensure_standard_directories()
    DATASETS_TEST_DIR.mkdir(parents=True, exist_ok=True)

    for existing in DATASETS_TEST_DIR.glob("*.jsonl"):
        existing.unlink()

    rng = random.Random(DEFAULT_SEED)
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source_directory": "datasets/final",
        "target_directory": "datasets/test",
        "seed": DEFAULT_SEED,
        "sample_sizes": DEFAULT_SAMPLE_SIZES,
        "files": [],
    }

    final_files = sorted(path for path in DATASETS_FINAL_DIR.glob("*.jsonl") if path.is_file())
    for src in final_files:
        questions = load_questions(src)
        type_tag = detect_type_tag(src, questions)
        sample_size = DEFAULT_SAMPLE_SIZES.get(type_tag)
        if not sample_size:
            continue
        sampled = round_robin_stratified_sample(questions, sample_size, rng)
        dst = DATASETS_TEST_DIR / f"test_{src.stem}_{len(sampled)}.jsonl"
        write_jsonl(dst, sampled)
        manifest["files"].append(
            {
                "source_file": src.name,
                "target_file": dst.name,
                "type_tag": type_tag,
                "source_count": len(questions),
                "sample_count": len(sampled),
                "difficulties": difficulty_counts(sampled),
            }
        )

    manifest_path = DATASETS_TEST_DIR / "test_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(manifest['files'])} test datasets in: {DATASETS_TEST_DIR}")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
