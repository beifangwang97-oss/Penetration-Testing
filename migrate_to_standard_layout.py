import json
import shutil
from pathlib import Path

from project_paths import (
    BASE_DIR,
    DATA_PROCESSED_DIR,
    DATASETS_FINAL_DIR,
    DATASETS_GENERATED_DIR,
    DATASETS_REVIEWED_DIR,
    LEGACY_ATTACK_DATA_PATH,
    LEGACY_EVALUATION_OUTPUT_DIR,
    LEGACY_OUTPUT_DIR,
    LEGACY_REVIEW_OUTPUT_DIR,
    RESULTS_ANALYSIS_DIR,
    RESULTS_EVALUATIONS_DIR,
    ensure_standard_directories,
)
from question_metadata import resolve_capability_dimension, resolve_question_form


QUESTION_FILE_SUFFIXES = {".json", ".jsonl"}


def flatten_reasoning_relative_path(rel: Path) -> Path:
    parts = rel.parts
    if parts and parts[0] == "reasoning":
        return Path(parts[-1])
    return rel


def normalize_question(question: dict) -> dict:
    normalized = dict(question)
    normalized["question_form"] = resolve_question_form(normalized)
    normalized["capability_dimension"] = resolve_capability_dimension(normalized)
    return normalized


def normalize_payload(payload):
    if isinstance(payload, dict):
        if "question_id" in payload:
            return normalize_question(payload)
        if "questions" in payload and isinstance(payload["questions"], list):
            updated = dict(payload)
            updated["questions"] = [normalize_question(item) if isinstance(item, dict) else item for item in payload["questions"]]
            return updated
        if "items" in payload and isinstance(payload["items"], list):
            updated = dict(payload)
            updated["items"] = [normalize_question(item) if isinstance(item, dict) else item for item in payload["items"]]
            return updated
        return payload
    if isinstance(payload, list):
        return [normalize_question(item) if isinstance(item, dict) else item for item in payload]
    return payload


def normalize_question_file(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8") as handle:
        raw_text = handle.read()

    if src.suffix.lower() == ".jsonl":
        lines = raw_text.splitlines()
        with dst.open("w", encoding="utf-8") as handle:
            for line in lines:
                if not line.strip():
                    continue
                item = json.loads(line)
                item = normalize_question(item) if isinstance(item, dict) else item
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        return "normalized-jsonl"

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        lines = [line for line in raw_text.splitlines() if line.strip()]
        with dst.open("w", encoding="utf-8") as handle:
            for line in lines:
                item = json.loads(line)
                item = normalize_question(item) if isinstance(item, dict) else item
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        return "normalized-json-as-jsonl"

    payload = normalize_payload(payload)
    with dst.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return "normalized-json"


def is_jsonl_text(raw_text: str) -> bool:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if len(lines) <= 1:
        return False
    try:
        for line in lines:
            json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


def copy_file(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copied"


def migrate_tree(src_root: Path, dst_root: Path, normalize_questions: bool) -> list[tuple[str, str, str]]:
    migrated = []
    if not src_root.exists():
        return migrated

    for src in sorted(path for path in src_root.rglob("*") if path.is_file()):
        rel = flatten_reasoning_relative_path(src.relative_to(src_root))
        dst = dst_root / rel
        if normalize_questions and src.suffix.lower() in QUESTION_FILE_SUFFIXES:
            action = normalize_question_file(src, dst)
        else:
            action = copy_file(src, dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))
    return migrated


def migrate_attack_data() -> list[tuple[str, str, str]]:
    migrated = []
    src = LEGACY_ATTACK_DATA_PATH
    dst = DATA_PROCESSED_DIR / "attack_data.json"
    if src.exists() and src.resolve() != dst.resolve():
        action = copy_file(src, dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))
    return migrated


def migrate_dataset_quality_outputs() -> list[tuple[str, str, str]]:
    migrated = []
    src_root = LEGACY_EVALUATION_OUTPUT_DIR
    dst_root = RESULTS_ANALYSIS_DIR / "dataset_quality"
    if not src_root.exists():
        return migrated
    for src in sorted(path for path in src_root.rglob("*") if path.is_file()):
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        action = copy_file(src, dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))
    return migrated


def standardize_jsonl_extensions(root: Path) -> list[tuple[str, str, str]]:
    migrated = []
    if not root.exists():
        return migrated

    for src in sorted(path for path in root.rglob("*.json") if path.is_file()):
        raw_text = src.read_text(encoding="utf-8")
        if not is_jsonl_text(raw_text):
            continue
        dst = src.with_suffix(".jsonl")
        if dst.exists():
            src.unlink()
            migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), "removed-duplicate-json"))
            continue
        src.rename(dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), "renamed-json-to-jsonl"))
    return migrated


def migrate_legacy_results() -> list[tuple[str, str, str]]:
    migrated = []
    results_root = BASE_DIR / "results"
    if not results_root.exists():
        return migrated

    standard_roots = {
        RESULTS_EVALUATIONS_DIR.resolve(),
        RESULTS_ANALYSIS_DIR.resolve(),
        (BASE_DIR / "results" / "reviews").resolve(),
    }

    for src in sorted(path for path in results_root.iterdir() if path.is_file()):
        dst = RESULTS_EVALUATIONS_DIR / src.name
        action = copy_file(src, dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))

    legacy_reasoning_dir = results_root / "reasoning"
    if legacy_reasoning_dir.exists():
        for src in sorted(path for path in legacy_reasoning_dir.rglob("*") if path.is_file()):
            if any(str(src.resolve()).startswith(str(root)) for root in standard_roots):
                continue
            rel = flatten_reasoning_relative_path(src.relative_to(legacy_reasoning_dir))
            dst = RESULTS_EVALUATIONS_DIR / rel
            action = copy_file(src, dst)
            migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))

    return migrated


def flatten_standard_reasoning_subdir(root: Path) -> list[tuple[str, str, str]]:
    migrated = []
    reasoning_dir = root / "reasoning"
    if not reasoning_dir.exists():
        return migrated

    for src in sorted(path for path in reasoning_dir.rglob("*") if path.is_file()):
        rel = flatten_reasoning_relative_path(src.relative_to(root))
        dst = root / rel
        if src.suffix.lower() in QUESTION_FILE_SUFFIXES:
            action = normalize_question_file(src, dst)
        else:
            action = copy_file(src, dst)
        migrated.append((str(src.relative_to(BASE_DIR)), str(dst.relative_to(BASE_DIR)), action))

    return migrated


def main() -> None:
    ensure_standard_directories()

    migrated: list[tuple[str, str, str]] = []
    migrated.extend(migrate_attack_data())
    migrated.extend(migrate_tree(LEGACY_OUTPUT_DIR, DATASETS_GENERATED_DIR, normalize_questions=True))
    migrated.extend(migrate_tree(LEGACY_REVIEW_OUTPUT_DIR, DATASETS_REVIEWED_DIR, normalize_questions=True))
    migrated.extend(migrate_legacy_results())
    migrated.extend(migrate_dataset_quality_outputs())
    migrated.extend(flatten_standard_reasoning_subdir(DATASETS_GENERATED_DIR))
    migrated.extend(flatten_standard_reasoning_subdir(DATASETS_REVIEWED_DIR))
    migrated.extend(flatten_standard_reasoning_subdir(DATASETS_FINAL_DIR))
    migrated.extend(flatten_standard_reasoning_subdir(RESULTS_EVALUATIONS_DIR))
    migrated.extend(standardize_jsonl_extensions(DATASETS_GENERATED_DIR))
    migrated.extend(standardize_jsonl_extensions(DATASETS_REVIEWED_DIR))

    summary = {
        "migrated_files": len(migrated),
        "entries": [
            {"source": src, "target": dst, "action": action}
            for src, dst, action in migrated
        ],
    }

    summary_path = RESULTS_ANALYSIS_DIR / "migration_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Migrated {len(migrated)} files.")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()
