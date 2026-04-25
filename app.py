import asyncio
import json
import os
import random
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv

from evaluate_models import ModelEvaluator


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"
DATASETS_DIR = BASE_DIR / "datasets"
OUTPUT_DIR = BASE_DIR / "output"
REVIEW_OUTPUT_DIR = BASE_DIR / "review_output"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
SUPPORTED_DATASET_SUFFIXES = {".json", ".jsonl"}


for directory in (UPLOAD_DIR, RESULTS_DIR, DATASETS_DIR, OUTPUT_DIR, REVIEW_OUTPUT_DIR, STATIC_DIR):
    directory.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")


DEFAULT_MODELS = [
    {
        "name": "GPT-4o",
        "model_id": "openai/gpt-4o",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Claude 3.5 Sonnet",
        "model_id": "anthropic/claude-3.5-sonnet",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Gemini 3.1 Flash Lite",
        "model_id": "google/gemini-3.1-flash-lite-preview",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Qwen 3.5 Flash",
        "model_id": "qwen/qwen3.5-flash-02-23",
        "api_key": "",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
]


def openrouter_env_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def list_dataset_paths() -> list[str]:
    datasets: list[str] = []
    scan_roots = (
        ("uploads", UPLOAD_DIR),
        ("datasets", DATASETS_DIR),
        ("output", OUTPUT_DIR),
        ("review_output", REVIEW_OUTPUT_DIR),
    )
    for directory_name, directory in scan_roots:
        for file_path in sorted(directory.rglob("*"), key=lambda item: str(item).lower()):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_DATASET_SUFFIXES:
                relative_path = file_path.relative_to(BASE_DIR).as_posix()
                datasets.append(relative_path)
    return datasets


def sanitize_filename(filename: str) -> str:
    return Path(filename).name


def resolve_dataset_path(dataset_path: str) -> Path | None:
    if not dataset_path:
        return None

    candidate = (BASE_DIR / dataset_path).resolve()
    allowed_roots = (
        UPLOAD_DIR.resolve(),
        DATASETS_DIR.resolve(),
        OUTPUT_DIR.resolve(),
        REVIEW_OUTPUT_DIR.resolve(),
    )
    if not any(str(candidate).startswith(str(root)) for root in allowed_roots):
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    if candidate.suffix.lower() not in SUPPORTED_DATASET_SUFFIXES:
        return None
    return candidate


def resolve_deletable_dataset_path(dataset_path: str) -> Path | None:
    candidate = resolve_dataset_path(dataset_path)
    if candidate is None:
        return None
    deletable_roots = (UPLOAD_DIR.resolve(), DATASETS_DIR.resolve())
    if not any(str(candidate).startswith(str(root)) for root in deletable_roots):
        return None
    return candidate


def model_api_key_for_runtime(model: dict) -> str:
    api_key = (model.get("api_key") or "").strip()
    endpoint = (model.get("endpoint") or "").strip()
    if api_key:
        return api_key
    if "openrouter.ai" in endpoint:
        return openrouter_env_key()
    return ""


async def handle_index(request: web.Request) -> web.Response:
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return web.Response(text=content, content_type="text/html")


async def handle_get_datasets(request: web.Request) -> web.Response:
    return web.json_response({"datasets": list_dataset_paths()})


async def handle_get_models(request: web.Request) -> web.Response:
    models = deepcopy(DEFAULT_MODELS)
    env_key_available = bool(openrouter_env_key())
    for model in models:
        model["env_key_available"] = env_key_available and "openrouter.ai" in model["endpoint"]
        model["api_key"] = ""
    return web.json_response({"status": "success", "models": models})


async def handle_upload_dataset(request: web.Request) -> web.Response:
    reader = await request.multipart()
    filepaths: list[str] = []

    while True:
        field = await reader.next()
        if field is None:
            break

        if field.name != "datasets" or not field.filename:
            continue

        filename = sanitize_filename(field.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_DATASET_SUFFIXES:
            continue

        filepath = UPLOAD_DIR / filename
        with filepath.open("wb") as handle:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                handle.write(chunk)

        filepaths.append(f"uploads/{filename}")

    if not filepaths:
        return web.json_response({"status": "error", "message": "No valid dataset files were uploaded."})

    return web.json_response({"status": "success", "filepaths": filepaths})


async def handle_delete_dataset(request: web.Request) -> web.Response:
    data = await request.json()
    dataset_path = data.get("path", "")
    resolved = resolve_deletable_dataset_path(dataset_path)

    if resolved is None:
        return web.json_response(
            {"status": "error", "message": "Only files under uploads/ or datasets/ can be deleted here."}
        )

    try:
        resolved.unlink()
        return web.json_response({"status": "success", "message": "Dataset deleted successfully."})
    except OSError as exc:
        return web.json_response({"status": "error", "message": f"Failed to delete dataset: {exc}"})


async def handle_start_evaluation(request: web.Request) -> web.Response:
    data = await request.json()
    dataset = data.get("dataset")
    models = data.get("models", [])

    dataset_paths = dataset if isinstance(dataset, list) else [dataset] if dataset else []
    valid_dataset_paths = [path for path in dataset_paths if resolve_dataset_path(path) is not None]

    if not valid_dataset_paths or not models:
        return web.json_response(
            {"status": "error", "message": "Please choose at least one valid dataset and one model."}
        )

    task_id = f"eval_{int(time.time())}_{random.randint(1000, 9999)}"
    asyncio.create_task(run_evaluation(task_id, valid_dataset_paths, models))
    return web.json_response({"status": "success", "task_id": task_id})


async def handle_get_progress(request: web.Request) -> web.Response:
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "task_id is required."})

    progress_file = RESULTS_DIR / f"{task_id}_progress.json"
    if not progress_file.exists():
        return web.json_response({"status": "error", "message": "Progress file not found."})

    progress = json.loads(progress_file.read_text(encoding="utf-8"))
    return web.json_response({"status": "success", "progress": progress})


async def handle_get_results(request: web.Request) -> web.Response:
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "task_id is required."})

    results_file = RESULTS_DIR / f"{task_id}_results.json"
    if not results_file.exists():
        return web.json_response({"status": "error", "message": "Results file not found."})

    results = json.loads(results_file.read_text(encoding="utf-8"))
    return web.json_response({"status": "success", "results": results})


async def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_evaluation(task_id: str, dataset_paths: list[str], models: list[dict]) -> None:
    progress_file = RESULTS_DIR / f"{task_id}_progress.json"
    progress: dict = {
        "task_id": task_id,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "current_dataset": 0,
        "total_datasets": len(dataset_paths),
        "current_dataset_path": "",
        "current_question": 0,
        "total_questions": 0,
        "current_question_id": "",
        "model_name": "",
        "percentage": 0,
    }

    try:
        await write_json(progress_file, progress)

        from evaluate_models import MODEL_CONFIGS

        MODEL_CONFIGS.clear()
        model_ids: list[str] = []

        for model in models:
            model_name = model.get("name")
            model_id = model.get("model_id")
            endpoint = model.get("endpoint", "https://openrouter.ai/api/v1/chat/completions")
            api_key = model_api_key_for_runtime(model)

            if not model_name or not model_id or not api_key:
                continue

            MODEL_CONFIGS[model_id] = {
                "name": model_name,
                "endpoint": endpoint,
                "api_key": api_key,
            }
            model_ids.append(model_id)

        if not model_ids:
            progress["status"] = "error"
            progress["error"] = "No usable model configuration was provided. Add an API key or use the local .env OpenRouter key."
            await write_json(progress_file, progress)
            return

        all_results: dict = {}
        all_result_files: list[dict] = []
        total_questions = 0

        for dataset_index, dataset_path in enumerate(dataset_paths, start=1):
            progress["status"] = "running"
            progress["current_dataset"] = dataset_index
            progress["current_dataset_path"] = dataset_path
            progress["percentage"] = 0
            await write_json(progress_file, progress)

            async def progress_callback(progress_data: dict) -> None:
                progress["status"] = progress_data.get("status", "running")
                progress["current_question"] = progress_data.get("current_question", 0)
                progress["total_questions"] = progress_data.get("total_questions", 0)
                progress["current_question_id"] = progress_data.get("current_question_id", "")
                progress["model_name"] = progress_data.get("model_name", "")
                if progress["total_questions"]:
                    progress["percentage"] = int(
                        progress["current_question"] / progress["total_questions"] * 100
                    )
                await write_json(progress_file, progress)

            evaluator = ModelEvaluator(
                dataset_path,
                model_ids,
                max_workers=3,
                progress_callback=progress_callback,
                model_configs=MODEL_CONFIGS,
            )
            await evaluator.run()

            for model_name in evaluator.results.keys():
                safe_model_name = model_name.replace(" ", "_")
                detailed_file = RESULTS_DIR / f"eval_{evaluator.task_id}_{safe_model_name}_detailed.jsonl"
                summary_file = RESULTS_DIR / f"eval_{evaluator.task_id}_{safe_model_name}_summary.json"

                if detailed_file.exists():
                    all_result_files.append(
                        {
                            "model_name": model_name,
                            "type": "detailed",
                            "filename": detailed_file.name,
                            "filepath": str(detailed_file),
                            "dataset": dataset_path,
                        }
                    )
                if summary_file.exists():
                    all_result_files.append(
                        {
                            "model_name": model_name,
                            "type": "summary",
                            "filename": summary_file.name,
                            "filepath": str(summary_file),
                            "dataset": dataset_path,
                        }
                    )

            for model_name, model_results in evaluator.results.items():
                if model_name not in all_results:
                    all_results[model_name] = {
                        "average_score": 0,
                        "accuracy": 0,
                        "total_questions": 0,
                        "correct": 0,
                        "incorrect": 0,
                        "total_score": 0,
                        "question_results": [],
                        "question_types": {},
                        "type_analysis": {},
                    }

                aggregate = all_results[model_name]
                aggregate["question_results"].extend(model_results.get("question_results", []))
                aggregate["total_questions"] += model_results.get("total_questions", 0)
                aggregate["correct"] += model_results.get("correct", 0)
                aggregate["incorrect"] += model_results.get("incorrect", 0)
                aggregate["total_score"] += model_results.get("total_score", 0)

                for q_type, stats in model_results.get("question_types", {}).items():
                    bucket = aggregate["question_types"].setdefault(
                        q_type, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
                    )
                    bucket["total"] += stats.get("total", 0)
                    bucket["correct"] += stats.get("correct", 0)
                    bucket["incorrect"] += stats.get("incorrect", 0)
                    bucket["total_score"] += stats.get("total_score", 0)

                for q_type, stats in model_results.get("type_analysis", {}).items():
                    bucket = aggregate["type_analysis"].setdefault(
                        q_type, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
                    )
                    bucket["total"] += stats.get("total", 0)
                    bucket["correct"] += stats.get("correct", 0)
                    bucket["incorrect"] += stats.get("incorrect", 0)
                    bucket["total_score"] += stats.get("total_score", 0)

            total_questions += len(evaluator.questions)

        for model_name, model_results in all_results.items():
            total = model_results["total_questions"]
            if total:
                model_results["average_score"] = model_results["total_score"] / total
                model_results["accuracy"] = model_results["correct"] / total

            for stats in model_results["question_types"].values():
                if stats["total"]:
                    stats["accuracy"] = stats["correct"] / stats["total"]
                    stats["average_score"] = stats["total_score"] / stats["total"]
                else:
                    stats["accuracy"] = 0
                    stats["average_score"] = 0

            for stats in model_results["type_analysis"].values():
                if stats["total"]:
                    stats["accuracy"] = stats["correct"] / stats["total"]
                    stats["average_score"] = stats["total_score"] / stats["total"]
                else:
                    stats["accuracy"] = 0
                    stats["average_score"] = 0

        if not all_results:
            for model in models:
                model_name = model.get("name", "Unknown Model")
                all_results[model_name] = {
                    "average_score": 0,
                    "accuracy": 0,
                    "total_questions": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "total_score": 0,
                    "question_results": [],
                    "question_types": {},
                    "type_analysis": {},
                }

        report = {
            "task_id": task_id,
            "datasets": dataset_paths,
            "models": [
                {
                    "name": model.get("name"),
                    "model_id": model.get("model_id"),
                    "endpoint": model.get("endpoint"),
                }
                for model in models
            ],
            "results": all_results,
            "total_questions": total_questions,
            "result_files": all_result_files,
            "start_time": progress["start_time"],
            "end_time": datetime.now().isoformat(),
        }

        await write_json(RESULTS_DIR / f"{task_id}_results.json", report)

        progress["status"] = "completed"
        progress["percentage"] = 100
        progress["end_time"] = datetime.now().isoformat()
        await write_json(progress_file, progress)

    except Exception as exc:
        progress["status"] = "error"
        progress["error"] = str(exc)
        progress["end_time"] = datetime.now().isoformat()
        await write_json(progress_file, progress)


app = web.Application()
app.add_routes(
    [
        web.get("/", handle_index),
        web.get("/api/datasets", handle_get_datasets),
        web.get("/api/models", handle_get_models),
        web.post("/api/upload", handle_upload_dataset),
        web.post("/api/delete-dataset", handle_delete_dataset),
        web.post("/api/start", handle_start_evaluation),
        web.get("/api/progress", handle_get_progress),
        web.get("/api/results", handle_get_results),
        web.static("/static", str(STATIC_DIR)),
        web.static("/uploads", str(UPLOAD_DIR)),
        web.static("/datasets", str(DATASETS_DIR)),
        web.static("/results", str(RESULTS_DIR)),
    ]
)


if __name__ == "__main__":
    print("Evaluation console is starting...")
    print("Open http://localhost:8084")
    web.run_app(app, port=8084)
