from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"

DATASETS_DIR = BASE_DIR / "datasets"
DATASETS_GENERATED_DIR = DATASETS_DIR / "generated"
DATASETS_REVIEWED_DIR = DATASETS_DIR / "reviewed"
DATASETS_FINAL_DIR = DATASETS_DIR / "final"
DATASETS_TEST_DIR = DATASETS_DIR / "test"

RESULTS_DIR = BASE_DIR / "results"
RESULTS_EVALUATIONS_DIR = RESULTS_DIR / "evaluations"
RESULTS_REVIEWS_DIR = RESULTS_DIR / "reviews"
RESULTS_ANALYSIS_DIR = RESULTS_DIR / "analysis"

UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

LEGACY_OUTPUT_DIR = BASE_DIR / "output"
LEGACY_REVIEW_OUTPUT_DIR = BASE_DIR / "review_output"
LEGACY_EVALUATION_OUTPUT_DIR = BASE_DIR / "evaluation_output"
LEGACY_ATTACK_DATA_PATH = DATA_DIR / "attack_data.json"

STANDARD_DIRECTORIES = (
    DATA_RAW_DIR,
    DATA_PROCESSED_DIR,
    DATASETS_GENERATED_DIR,
    DATASETS_REVIEWED_DIR,
    DATASETS_FINAL_DIR,
    DATASETS_TEST_DIR,
    RESULTS_EVALUATIONS_DIR,
    RESULTS_REVIEWS_DIR,
    RESULTS_ANALYSIS_DIR,
    UPLOAD_DIR,
    STATIC_DIR,
)


def ensure_standard_directories() -> None:
    for directory in STANDARD_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def attack_data_path() -> Path:
    preferred = DATA_PROCESSED_DIR / "attack_data.json"
    if preferred.exists():
        return preferred
    return LEGACY_ATTACK_DATA_PATH


def dataset_scan_roots() -> tuple[tuple[str, Path], ...]:
    return (
        ("uploads", UPLOAD_DIR),
        ("datasets/test", DATASETS_TEST_DIR),
        ("datasets/final", DATASETS_FINAL_DIR),
        ("datasets/reviewed", DATASETS_REVIEWED_DIR),
        ("datasets/generated", DATASETS_GENERATED_DIR),
        ("datasets", DATASETS_DIR),
    )
