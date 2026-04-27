import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from project_paths import DATASETS_FINAL_DIR, DATASETS_REVIEWED_DIR, RESULTS_ANALYSIS_DIR, ensure_standard_directories


def is_freezable_review_file(path: Path) -> bool:
    name = path.name
    if path.suffix.lower() != ".jsonl":
        return False
    if not name.startswith("review_"):
        return False
    if name.startswith("review_修改记录_"):
        return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_reviewed_to_final() -> list[tuple[Path, Path]]:
    copied = []
    for existing in DATASETS_FINAL_DIR.glob("*.jsonl"):
        existing.unlink()

    for src in sorted(path for path in DATASETS_REVIEWED_DIR.rglob("*.jsonl") if is_freezable_review_file(path)):
        rel = src.relative_to(DATASETS_REVIEWED_DIR)
        dst = DATASETS_FINAL_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append((src, dst))
    return copied


def build_duplicate_report(final_files: list[Path]) -> dict:
    report = {"generated_at": datetime.now().isoformat(), "files": []}

    for path in final_files:
        seen_question_texts: dict[str, list[str]] = defaultdict(list)
        seen_scenario_texts: dict[str, list[str]] = defaultdict(list)
        total = 0

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            total += 1
            question_id = item.get("question_id", "")
            question_text = (item.get("question", "") or "").strip()
            scenario_text = (item.get("scenario", "") or "").strip()
            if question_text:
                seen_question_texts[question_text].append(question_id)
            if scenario_text:
                seen_scenario_texts[scenario_text].append(question_id)

        duplicate_questions = [
            {"question_text": key, "question_ids": ids, "count": len(ids)}
            for key, ids in seen_question_texts.items()
            if len(ids) > 1
        ]
        duplicate_scenarios = [
            {"scenario_text": key, "question_ids": ids, "count": len(ids)}
            for key, ids in seen_scenario_texts.items()
            if len(ids) > 1
        ]

        report["files"].append(
            {
                "file": str(path.relative_to(DATASETS_FINAL_DIR)).replace("\\", "/"),
                "total_questions": total,
                "duplicate_question_groups": len(duplicate_questions),
                "duplicate_question_items": sum(item["count"] for item in duplicate_questions),
                "duplicate_scenario_groups": len(duplicate_scenarios),
                "duplicate_scenario_items": sum(item["count"] for item in duplicate_scenarios),
                "sample_duplicate_questions": duplicate_questions[:20],
                "sample_duplicate_scenarios": duplicate_scenarios[:20],
            }
        )

    return report


def build_manifest(final_files: list[Path]) -> dict:
    manifest = {
        "frozen_at": datetime.now().isoformat(),
        "source_directory": str(DATASETS_REVIEWED_DIR.relative_to(DATASETS_REVIEWED_DIR.parent)).replace("\\", "/"),
        "target_directory": str(DATASETS_FINAL_DIR.relative_to(DATASETS_FINAL_DIR.parent)).replace("\\", "/"),
        "files": [],
        "totals": {
            "files": 0,
            "questions": 0,
            "by_question_form": {},
            "by_capability_dimension": {},
        },
    }

    total_by_form: defaultdict[str, int] = defaultdict(int)
    total_by_dimension: defaultdict[str, int] = defaultdict(int)
    total_questions = 0

    for path in final_files:
        per_form: defaultdict[str, int] = defaultdict(int)
        per_dimension: defaultdict[str, int] = defaultdict(int)
        count = 0

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            count += 1
            question_form = item.get("question_form", "unknown")
            capability_dimension = item.get("capability_dimension", "unknown")
            per_form[question_form] += 1
            per_dimension[capability_dimension] += 1
            total_by_form[question_form] += 1
            total_by_dimension[capability_dimension] += 1

        total_questions += count
        manifest["files"].append(
            {
                "file": str(path.relative_to(DATASETS_FINAL_DIR)).replace("\\", "/"),
                "question_count": count,
                "sha256": sha256_file(path),
                "by_question_form": dict(sorted(per_form.items())),
                "by_capability_dimension": dict(sorted(per_dimension.items())),
            }
        )

    manifest["totals"]["files"] = len(final_files)
    manifest["totals"]["questions"] = total_questions
    manifest["totals"]["by_question_form"] = dict(sorted(total_by_form.items()))
    manifest["totals"]["by_capability_dimension"] = dict(sorted(total_by_dimension.items()))
    return manifest


def main() -> None:
    ensure_standard_directories()
    copied_pairs = copy_reviewed_to_final()
    final_files = [dst for _, dst in copied_pairs]

    manifest = build_manifest(final_files)
    duplicate_report = build_duplicate_report(final_files)

    manifest_path = DATASETS_FINAL_DIR / "final_manifest.json"
    duplicate_report_path = RESULTS_ANALYSIS_DIR / "final_duplicate_report.json"

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    duplicate_report_path.write_text(json.dumps(duplicate_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Frozen {len(final_files)} dataset files into: {DATASETS_FINAL_DIR}")
    print(f"Manifest written to: {manifest_path}")
    print(f"Duplicate report written to: {duplicate_report_path}")


if __name__ == "__main__":
    main()
