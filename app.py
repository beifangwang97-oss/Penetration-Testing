import asyncio
import json
import os
import random
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web
from dotenv import load_dotenv

from evaluate_models import ModelEvaluator
from project_paths import (
    BASE_DIR,
    DATASETS_DIR,
    RESULTS_DIR,
    RESULTS_EVALUATIONS_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOAD_DIR,
    dataset_scan_roots,
    ensure_standard_directories,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SUPPORTED_DATASET_SUFFIXES = {".json", ".jsonl"}


ensure_standard_directories()

load_dotenv(BASE_DIR / ".env")


DEFAULT_MODELS = [
    {
        "name": "Gemini 3.1 Flash Lite",
        "model_id": "google/gemini-3.1-flash-lite-preview",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Qwen 3.5 Flash",
        "model_id": "qwen/qwen3.5-flash-02-23",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "GPT-4o Mini",
        "model_id": "openai/gpt-4o-mini",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Doubao Seed 1.6 Flash",
        "model_id": "bytedance-seed/seed-1.6-flash",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "DeepSeek V3.2",
        "model_id": "deepseek/deepseek-v3.2",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
]

MODEL_CATALOG = [
    *DEFAULT_MODELS,
    {
        "name": "Claude 3.5 Sonnet",
        "model_id": "anthropic/claude-3.5-sonnet",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "GPT-4o",
        "model_id": "openai/gpt-4o",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Claude Haiku 4.5",
        "model_id": "anthropic/claude-haiku-4.5",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Claude 3.7 Sonnet",
        "model_id": "anthropic/claude-3.7-sonnet",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Gemini 2.5 Pro",
        "model_id": "google/gemini-2.5-pro-preview",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
    {
        "name": "Qwen Max",
        "model_id": "qwen/qwen-max",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
    },
]

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
API_TEST_MODEL_ID = "openai/gpt-4o-mini"


def openrouter_env_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def list_dataset_paths() -> list[str]:
    datasets: list[str] = []
    for directory_name, directory in dataset_scan_roots():
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


def slugify(value: str) -> str:
    lowered = (value or "unknown").lower().replace("\\", "/")
    cleaned = []
    for char in lowered:
        if char.isalnum():
            cleaned.append(char)
        elif char in {"/", "-", "_", ".", " "}:
            cleaned.append("_" if char == "/" else char)
        else:
            cleaned.append("_")
    slug = "".join(cleaned).replace(" ", "-")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("._-") or "unknown"


def task_dir_for(task_id: str) -> Path:
    return RESULTS_EVALUATIONS_DIR / task_id


def progress_file_for(task_id: str) -> Path:
    return task_dir_for(task_id) / "progress.json"


def report_file_for(task_id: str) -> Path:
    return task_dir_for(task_id) / "final_report.json"


def manifest_file_for(task_id: str) -> Path:
    return task_dir_for(task_id) / "manifest.json"


def model_display_label(model_name: str, model_id: str) -> str:
    return f"{model_name} | {model_id}"


async def handle_index(request: web.Request) -> web.Response:
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return web.Response(text=content, content_type="text/html")


async def handle_get_datasets(request: web.Request) -> web.Response:
    return web.json_response({"datasets": list_dataset_paths()})


async def handle_get_models(request: web.Request) -> web.Response:
    models = deepcopy(DEFAULT_MODELS)
    catalog = deepcopy(MODEL_CATALOG)
    return web.json_response({"status": "success", "models": models, "catalog": catalog})


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
    api_keys = [str(item).strip() for item in data.get("api_keys", []) if str(item).strip()]

    dataset_paths = dataset if isinstance(dataset, list) else [dataset] if dataset else []
    valid_dataset_paths = [path for path in dataset_paths if resolve_dataset_path(path) is not None]

    if not valid_dataset_paths or not models or not api_keys:
        return web.json_response(
            {"status": "error", "message": "Please choose at least one valid dataset, one model, and one API key."}
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"eval_{timestamp}_{random.randint(1000, 9999)}"
    asyncio.create_task(run_evaluation(task_id, valid_dataset_paths, models, api_keys))
    return web.json_response({"status": "success", "task_id": task_id})


async def test_openrouter_key(session: ClientSession, api_key: str, index: int) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": API_TEST_MODEL_ID,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }

    try:
        async with session.post(OPENROUTER_ENDPOINT, headers=headers, json=payload) as response:
            text = await response.text()
            if response.status == 200:
                return {"index": index, "ok": True, "message": "联通成功"}

            message = f"HTTP {response.status}"
            try:
                error_payload = json.loads(text)
                nested_error = error_payload.get("error") or {}
                if isinstance(nested_error, dict):
                    message = nested_error.get("message") or nested_error.get("code") or message
                elif isinstance(nested_error, str) and nested_error.strip():
                    message = nested_error.strip()
            except json.JSONDecodeError:
                if text.strip():
                    message = text.strip()[:120]
            return {"index": index, "ok": False, "message": message}
    except asyncio.TimeoutError:
        return {"index": index, "ok": False, "message": "请求超时"}
    except Exception as exc:
        return {"index": index, "ok": False, "message": str(exc)}


async def handle_test_api_keys(request: web.Request) -> web.Response:
    data = await request.json()
    api_keys = [str(item).strip() for item in data.get("api_keys", []) if str(item).strip()]

    if not api_keys:
        return web.json_response({"status": "error", "message": "Please provide at least one API key."})

    timeout = ClientTimeout(total=20)
    async with ClientSession(timeout=timeout) as session:
        results = await asyncio.gather(
            *(test_openrouter_key(session, api_key, index) for index, api_key in enumerate(api_keys)),
            return_exceptions=False,
        )

    return web.json_response({"status": "success", "results": results})


async def handle_get_progress(request: web.Request) -> web.Response:
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "task_id is required."})

    progress_file = progress_file_for(task_id)
    if not progress_file.exists():
        return web.json_response({"status": "error", "message": "Progress file not found."})

    progress = json.loads(progress_file.read_text(encoding="utf-8"))
    return web.json_response({"status": "success", "progress": progress})


async def handle_get_results(request: web.Request) -> web.Response:
    task_id = request.query.get("task_id")
    if not task_id:
        return web.json_response({"status": "error", "message": "task_id is required."})

    results_file = report_file_for(task_id)
    if not results_file.exists():
        return web.json_response({"status": "error", "message": "Results file not found."})

    results = json.loads(results_file.read_text(encoding="utf-8"))
    return web.json_response({"status": "success", "results": results})


async def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def empty_aggregate(model_name: str, model_id: str, endpoint: str) -> dict:
    return {
        "model_name": model_name,
        "model_id": model_id,
        "endpoint": endpoint,
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


def merge_summary(aggregate: dict, summary: dict) -> None:
    aggregate["question_results"].extend(summary.get("question_results", []))
    aggregate["total_questions"] += summary.get("total_questions", 0)
    aggregate["correct"] += summary.get("correct", 0)
    aggregate["incorrect"] += summary.get("incorrect", 0)
    aggregate["total_score"] += summary.get("total_score", 0)

    for q_type, stats in summary.get("question_types", {}).items():
        bucket = aggregate["question_types"].setdefault(
            q_type, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
        )
        bucket["total"] += stats.get("total", 0)
        bucket["correct"] += stats.get("correct", 0)
        bucket["incorrect"] += stats.get("incorrect", 0)
        bucket["total_score"] += stats.get("total_score", 0)

    for q_type, stats in summary.get("type_analysis", {}).items():
        bucket = aggregate["type_analysis"].setdefault(
            q_type, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0}
        )
        bucket["total"] += stats.get("total", 0)
        bucket["correct"] += stats.get("correct", 0)
        bucket["incorrect"] += stats.get("incorrect", 0)
        bucket["total_score"] += stats.get("total_score", 0)


def finalize_aggregate(aggregate: dict) -> dict:
    total = aggregate["total_questions"]
    aggregate["average_score"] = aggregate["total_score"] / total if total else 0
    aggregate["accuracy"] = aggregate["correct"] / total if total else 0

    for stats in aggregate["question_types"].values():
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] else 0
        stats["average_score"] = stats["total_score"] / stats["total"] if stats["total"] else 0

    for stats in aggregate["type_analysis"].values():
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] else 0
        stats["average_score"] = stats["total_score"] / stats["total"] if stats["total"] else 0

    return aggregate


async def run_evaluation(task_id: str, dataset_paths: list[str], models: list[dict], api_keys: list[str]) -> None:
    task_dir = task_dir_for(task_id)
    progress_file = progress_file_for(task_id)
    report_file = report_file_for(task_id)
    manifest_file = manifest_file_for(task_id)
    models_dir = task_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    progress_lock = asyncio.Lock()
    report_lock = asyncio.Lock()

    normalized_models = []
    for index, model in enumerate(models):
        model_name = str(model.get("name") or "").strip()
        model_id = str(model.get("model_id") or "").strip()
        endpoint = str(model.get("endpoint") or "https://openrouter.ai/api/v1/chat/completions").strip()
        if not model_name or not model_id:
            continue
        normalized_models.append(
            {
                "index": index,
                "name": model_name,
                "model_id": model_id,
                "endpoint": endpoint,
                "label": model_display_label(model_name, model_id),
                "slug": slugify(f"{model_name}__{model_id}"),
            }
        )

    api_slots = [{"slot": f"API-{index + 1}", "api_key": key} for index, key in enumerate(api_keys) if key]

    progress = {
        "task_id": task_id,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "datasets": dataset_paths,
        "api_slots": [item["slot"] for item in api_slots],
        "dataset_count": len(dataset_paths),
        "model_count": len(normalized_models),
        "api_key_count": len(api_slots),
        "model_order": [model["label"] for model in normalized_models],
        "models": {},
    }

    aggregates: dict[str, dict] = {}
    result_files: list[dict] = []

    for model in normalized_models:
        progress["models"][model["label"]] = {
            "model_name": model["name"],
            "model_id": model["model_id"],
            "endpoint": model["endpoint"],
            "api_slot": None,
            "status": "pending",
            "datasets": {
                dataset_path: {"done": 0, "total": 0, "status": "pending"}
                for dataset_path in dataset_paths
            },
        }
        aggregates[model["label"]] = empty_aggregate(model["name"], model["model_id"], model["endpoint"])

    manifest = {
        "task_id": task_id,
        "start_time": progress["start_time"],
        "datasets": dataset_paths,
        "models": [
            {"name": model["name"], "model_id": model["model_id"], "endpoint": model["endpoint"], "label": model["label"]}
            for model in normalized_models
        ],
        "api_slots": [item["slot"] for item in api_slots],
    }

    async def write_progress() -> None:
        async with progress_lock:
            await write_json(progress_file, progress)

    async def write_report_snapshot(status: str) -> None:
        async with report_lock:
            snapshot_results = {
                label: finalize_aggregate(
                    {
                        **aggregate,
                        "question_results": list(aggregate["question_results"]),
                        "question_types": json.loads(json.dumps(aggregate["question_types"])),
                        "type_analysis": json.loads(json.dumps(aggregate["type_analysis"])),
                    }
                )
                for label, aggregate in aggregates.items()
            }
            await write_json(
                report_file,
                {
                    "task_id": task_id,
                    "status": status,
                    "datasets": dataset_paths,
                    "models": [
                        {"name": model["name"], "model_id": model["model_id"], "endpoint": model["endpoint"]}
                        for model in normalized_models
                    ],
                    "results": snapshot_results,
                    "total_questions": sum(item["total_questions"] for item in snapshot_results.values()),
                    "result_files": result_files,
                    "start_time": progress["start_time"],
                    "end_time": progress.get("end_time"),
                },
            )

    try:
        if not normalized_models or not api_slots:
            progress["status"] = "error"
            progress["end_time"] = datetime.now().isoformat()
            progress["error"] = "No usable model or API key was provided."
            await write_json(progress_file, progress)
            await write_json(manifest_file, manifest)
            return

        await write_json(manifest_file, manifest)
        await write_progress()
        await write_report_snapshot("running")

        queue: asyncio.Queue[dict] = asyncio.Queue()
        for model in normalized_models:
            await queue.put(model)

        async def worker(api_slot: dict) -> None:
            while True:
                try:
                    model = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return

                label = model["label"]
                model_state = progress["models"][label]
                model_state["api_slot"] = api_slot["slot"]
                model_state["status"] = "running"
                await write_progress()

                model_result_dir = models_dir / model["slug"]
                model_result_dir.mkdir(parents=True, exist_ok=True)

                for dataset_path in dataset_paths:
                    dataset_state = model_state["datasets"][dataset_path]
                    dataset_state["status"] = "running"
                    await write_progress()

                    dataset_resolved = resolve_dataset_path(dataset_path)
                    if dataset_resolved is None:
                        dataset_state["status"] = "error"
                        await write_progress()
                        continue

                    dataset_slug = slugify(dataset_path)
                    detailed_name = f"{dataset_slug}.jsonl"
                    dataset_summary_name = f"{dataset_slug}_summary.json"

                    async def dataset_progress_callback(progress_data: dict) -> None:
                        dataset_state["done"] = progress_data.get("current_question", 0)
                        dataset_state["total"] = progress_data.get("total_questions", 0)
                        dataset_state["status"] = "completed" if progress_data.get("status") == "completed" else "running"
                        await write_progress()

                    evaluator = ModelEvaluator(
                        str(dataset_resolved),
                        models=[model["model_id"]],
                        max_workers=3,
                        progress_callback=dataset_progress_callback,
                        model_configs={
                            model["model_id"]: {
                                "name": model["name"],
                                "endpoint": model["endpoint"],
                                "api_key": api_slot["api_key"],
                            }
                        },
                        result_dir=model_result_dir,
                        task_id=task_id,
                        detailed_filename=detailed_name,
                        summary_filename=dataset_summary_name,
                    )

                    try:
                        await evaluator.run()
                        summary = evaluator.results.get(model["name"])
                        if summary:
                            merge_summary(aggregates[label], summary)
                            finalize_aggregate(aggregates[label])
                            dataset_state["done"] = dataset_state["total"] or summary.get("total_questions", 0)
                            dataset_state["total"] = dataset_state["total"] or summary.get("total_questions", 0)
                            dataset_state["status"] = "completed"
                            await write_json(model_result_dir / "summary.json", aggregates[label])
                            result_files.append(
                                {
                                    "model_name": model["name"],
                                    "model_id": model["model_id"],
                                    "type": "detailed",
                                    "filename": detailed_name,
                                    "filepath": str((model_result_dir / detailed_name).resolve()),
                                    "dataset": dataset_path,
                                }
                            )
                    except Exception as exc:
                        dataset_state["status"] = "error"
                        model_state["status"] = "error"
                        model_state["error"] = str(exc)
                    finally:
                        await write_progress()
                        await write_report_snapshot("running")

                if model_state["status"] != "error":
                    model_state["status"] = "completed"
                await write_progress()
                await write_report_snapshot("running")
                queue.task_done()

        await asyncio.gather(*(worker(api_slot) for api_slot in api_slots))

        progress["status"] = "completed"
        progress["end_time"] = datetime.now().isoformat()
        await write_progress()
        await write_report_snapshot("completed")

    except Exception as exc:
        progress["status"] = "error"
        progress["error"] = str(exc)
        progress["end_time"] = datetime.now().isoformat()
        await write_progress()
        await write_report_snapshot("error")


app = web.Application()
app.add_routes(
    [
        web.get("/", handle_index),
        web.get("/api/datasets", handle_get_datasets),
        web.get("/api/models", handle_get_models),
        web.post("/api/upload", handle_upload_dataset),
        web.post("/api/delete-dataset", handle_delete_dataset),
        web.post("/api/start", handle_start_evaluation),
        web.post("/api/test-api-keys", handle_test_api_keys),
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
