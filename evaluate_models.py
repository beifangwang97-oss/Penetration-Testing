import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from aiohttp import ClientSession
from dotenv import load_dotenv

from attack_id_aliases import canonicalize_attack_id, canonicalize_attack_ids
from project_paths import DATASETS_FINAL_DIR, RESULTS_EVALUATIONS_DIR, ensure_standard_directories
from question_metadata import resolve_capability_dimension, resolve_question_form

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

DATASETS_DIR = str(DATASETS_FINAL_DIR)
RESULTS_DIR = str(RESULTS_EVALUATIONS_DIR)
MODEL_CONFIGS: dict[str, dict] = {}
API_TIMEOUT_SECONDS = 60
API_RETRY_COUNT = 3

ensure_standard_directories()
os.makedirs(RESULTS_DIR, exist_ok=True)


class ModelEvaluator:
    def __init__(
        self,
        dataset_path,
        models=None,
        max_workers=3,
        progress_callback=None,
        model_configs=None,
        result_dir=None,
        task_id=None,
        detailed_filename=None,
        summary_filename=None,
    ):
        self.dataset_path = dataset_path
        self.models = models or []
        self.questions = []
        self.results = {}
        self.task_id = task_id or datetime.now().strftime("%Y%m%d%H%M%S")
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.model_configs = model_configs or {}
        self.result_dir = Path(result_dir) if result_dir else Path(RESULTS_DIR)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.detailed_filename = detailed_filename
        self.summary_filename = summary_filename

    def extract_single_choice(self, answer):
        if not answer:
            return ""
        answer = str(answer).upper()
        match = re.search(r"[A-D]", answer)
        return match.group(0) if match else ""

    def extract_multiple_choices(self, answer):
        if not answer:
            return []
        if isinstance(answer, list):
            return sorted([str(item).upper() for item in answer])
        if isinstance(answer, str):
            return sorted(set(re.findall(r"[A-D]", answer.upper())))
        return []

    def extract_sequence(self, answer):
        if not answer:
            return []
        if isinstance(answer, list):
            return [str(item).upper() for item in answer]
        if isinstance(answer, str):
            return re.findall(r"[A-D]", answer.upper())
        return []

    def extract_attack_ids(self, answer):
        if not answer:
            return []
        if isinstance(answer, list):
            text = " ".join(str(item) for item in answer)
        else:
            text = str(answer)
        return [item.upper() for item in re.findall(r"T\d{4}(?:\.\d{3})?", text, flags=re.IGNORECASE)]

    async def load_dataset(self):
        print(f"Loading dataset: {self.dataset_path}")
        self.questions = []
        try:
            with open(self.dataset_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        self.questions.append(json.loads(line))
            print(f"Loaded {len(self.questions)} questions")
            return True
        except Exception as exc:
            print(f"Failed to load dataset: {exc}")
            return False

    async def test_model(self, model_id, session):
        model_config = self.model_configs.get(model_id)
        if not model_config:
            print(f"Model {model_id} is missing configuration, skipping.")
            return

        model_name = model_config["name"]
        endpoint = model_config["endpoint"]
        api_key = model_config["api_key"]

        if not api_key:
            print(f"Model {model_name} is missing an API key, skipping.")
            return

        print(f"Evaluating model: {model_name}")

        model_results = {
            "model_id": model_id,
            "model_name": model_name,
            "total_questions": len(self.questions),
            "correct": 0,
            "incorrect": 0,
            "question_results": [],
            "start_time": datetime.now().isoformat(),
            "end_time": None,
        }

        semaphore = asyncio.Semaphore(self.max_workers)

        async def test_single_question(index, question):
            async with semaphore:
                question_id = question.get("question_id", "")
                question_type = question.get("question_type") or self.detect_question_type(question_id)
                test_prompt = question.get("test_prompt")
                correct_answer = question.get("correct_answer")
                current_question = index + 1
                total_questions = len(self.questions)

                if self.progress_callback:
                    await self.progress_callback(
                        {
                            "status": "running",
                            "current_question": current_question,
                            "total_questions": total_questions,
                            "current_question_id": question_id,
                            "model_name": model_name,
                        }
                    )

                model_answer = await self.call_model_api(session, endpoint, api_key, model_id, test_prompt)
                is_correct, score = self.judge_answer(
                    model_answer,
                    correct_answer,
                    question_type,
                    question_id,
                    question=question,
                )

                question_result = {
                    "question_id": question_id,
                    "question_type": question_type,
                    "question_form": resolve_question_form(question),
                    "capability_dimension": resolve_capability_dimension(question),
                    "question": question.get("question"),
                    "test_prompt": test_prompt,
                    "model_answer": model_answer,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "score": score,
                }

                await self.write_question_result(model_name, question_result)
                return question_result

        question_results = await asyncio.gather(
            *(test_single_question(index, question) for index, question in enumerate(self.questions))
        )

        for result in question_results:
            model_results["question_results"].append(result)
            if result["is_correct"]:
                model_results["correct"] += 1
            else:
                model_results["incorrect"] += 1

        model_results["end_time"] = datetime.now().isoformat()
        model_results["accuracy"] = (
            model_results["correct"] / len(self.questions) if self.questions else 0
        )

        model_summary = self.generate_model_summary(model_results)
        self.results[model_name] = model_summary
        await self.save_model_results(model_name, model_summary)

        if self.progress_callback:
            await self.progress_callback(
                {
                    "status": "completed",
                    "current_question": len(self.questions),
                    "total_questions": len(self.questions),
                    "current_question_id": "",
                    "model_name": model_name,
                }
            )

        print(
            f"Model finished: {model_name}, accuracy={model_summary['accuracy']:.2%}, "
            f"correct={model_summary['correct']}, incorrect={model_summary['incorrect']}"
        )

    async def call_model_api(self, session, endpoint, api_key, model_id, prompt):
        total_attempts = API_RETRY_COUNT + 1
        for attempt in range(1, total_attempts + 1):
            try:
                if "generativelanguage.googleapis.com" in endpoint:
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
                    }
                    async with session.post(
                        f"{endpoint}?key={api_key}",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=API_TIMEOUT_SECONDS,
                    ) as response:
                        if response.status != 200:
                            print(f"Gemini API error {response.status}: {await response.text()}")
                            return ""
                        data = await response.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100,
                }
                async with session.post(
                    endpoint,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://penetration-testing-demo",
                        "X-Title": "Penetration Testing Demo",
                    },
                    json=payload,
                    timeout=API_TIMEOUT_SECONDS,
                ) as response:
                    if response.status != 200:
                        print(f"Chat API error {response.status}: {await response.text()}")
                        return ""
                    data = await response.json()
                    try:
                        return data["choices"][0]["message"]["content"].strip()
                    except (KeyError, IndexError, TypeError):
                        print(f"Unexpected API response: {json.dumps(data, ensure_ascii=False)}")
                        return ""
            except asyncio.TimeoutError:
                print(
                    f"API call timed out (attempt {attempt}/{total_attempts}, timeout={API_TIMEOUT_SECONDS}s)"
                )
                if attempt < total_attempts:
                    await asyncio.sleep(min(2 * attempt, 5))
                    continue
                return ""
            except Exception as exc:
                print(f"API call failed: {exc}")
                return ""

        return ""

    def detect_question_type(self, question_id):
        if question_id.startswith("SSC-"):
            return "single_choice"
        if question_id.startswith("SC-"):
            return "single_choice"
        if question_id.startswith("MC-"):
            return "multiple_choice"
        if question_id.startswith("JU-"):
            return "judgment"
        if question_id.startswith("SQ-"):
            return "sequencing"
        if question_id.startswith("SAR-"):
            return "short_answer_reasoning"
        if question_id.startswith("MSR-"):
            return "scenario_multi_step_reasoning"
        return "UNKNOWN"

    def judge_answer(self, model_answer, correct_answer, question_type, question_id=None, question=None):
        actual_type = question_type
        if question_id:
            detected_type = self.detect_question_type(question_id)
            if detected_type != "UNKNOWN":
                actual_type = detected_type

        if actual_type in {"SC", "SSC", "single_choice"}:
            model_choice = self.extract_single_choice(model_answer)
            correct_choice = self.extract_single_choice(correct_answer)
            is_correct = model_choice == correct_choice
            return is_correct, 1.0 if is_correct else 0.0

        if actual_type in {"MC", "multiple_choice"}:
            model_set = set(self.extract_multiple_choices(model_answer))
            correct_set = set(self.extract_multiple_choices(correct_answer))
            if model_set == correct_set:
                return True, 1.0
            if model_set and model_set.issubset(correct_set):
                return False, 0.5
            return False, 0.0

        if actual_type in {"JU", "judgment"}:
            def normalize_judgment(answer):
                normalized = str(answer or "").strip().lower()
                for token in ["。", "，", "；", "：", ".", ",", "!", "?", "！", "？"]:
                    normalized = normalized.replace(token, "")
                return normalized

            is_correct = normalize_judgment(model_answer) == normalize_judgment(correct_answer)
            return is_correct, 1.0 if is_correct else 0.0

        if actual_type in {"SQ", "sequencing"}:
            model_list = self.extract_sequence(model_answer)
            correct_list = self.extract_sequence(correct_answer)
            model_list = model_list[: len(correct_list)]
            if model_list == correct_list:
                return True, 1.0
            correct_positions = {item: index for index, item in enumerate(correct_list)}
            total_pairs = len(correct_list) * (len(correct_list) - 1) // 2
            if total_pairs <= 0:
                return False, 0.0
            correct_order = 0
            for left in range(len(model_list)):
                for right in range(left + 1, len(model_list)):
                    if (
                        model_list[left] in correct_positions
                        and model_list[right] in correct_positions
                        and correct_positions[model_list[left]] < correct_positions[model_list[right]]
                    ):
                        correct_order += 1
            similarity = correct_order / total_pairs
            return False, 0.6 if similarity >= 0.7 else 0.0

        if actual_type == "scenario_multi_step_reasoning":
            model_list = self.extract_sequence(model_answer)
            correct_list = self.extract_sequence(correct_answer)
            model_list = model_list[: len(correct_list)]
            if model_list == correct_list:
                return True, 1.0
            if model_list and correct_list:
                matched = sum(1 for left, right in zip(model_list, correct_list) if left == right)
                return False, round(matched / len(correct_list), 3)
            return False, 0.0

        if actual_type == "short_answer_reasoning":
            model_ids = canonicalize_attack_ids(self.extract_attack_ids(model_answer))
            target_ids = []
            if isinstance(question, dict):
                target_ids = canonicalize_attack_ids(
                    [str(item).upper() for item in question.get("target_techniques", []) if item]
                )
            correct_ids = target_ids or canonicalize_attack_ids(self.extract_attack_ids(correct_answer))
            if correct_ids:
                if any(item in correct_ids for item in model_ids):
                    return True, 1.0
                parent_correct = {canonicalize_attack_id(item.split(".")[0]) for item in correct_ids}
                parent_model = {canonicalize_attack_id(item.split(".")[0]) for item in model_ids}
                if parent_correct & parent_model:
                    return False, 0.5
                return False, 0.0

        is_correct = str(model_answer).strip() == str(correct_answer).strip()
        return is_correct, 1.0 if is_correct else 0.0

    def generate_model_summary(self, model_results):
        question_types = {}
        type_analysis = {}
        total_score = 0.0

        for result in model_results["question_results"]:
            question_form = result.get("question_form") or result["question_type"]
            question_bucket = question_types.setdefault(
                question_form, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0.0}
            )
            question_bucket["total"] += 1
            question_bucket["correct"] += 1 if result["is_correct"] else 0
            question_bucket["incorrect"] += 0 if result["is_correct"] else 1
            question_bucket["total_score"] += result.get("score", 0.0)

            capability = result.get("capability_dimension") or result["question_type"]
            capability_bucket = type_analysis.setdefault(
                capability, {"total": 0, "correct": 0, "incorrect": 0, "total_score": 0.0}
            )
            capability_bucket["total"] += 1
            capability_bucket["correct"] += 1 if result["is_correct"] else 0
            capability_bucket["incorrect"] += 0 if result["is_correct"] else 1
            capability_bucket["total_score"] += result.get("score", 0.0)

            total_score += result.get("score", 0.0)

        for stats in question_types.values():
            stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] else 0
            stats["average_score"] = stats["total_score"] / stats["total"] if stats["total"] else 0

        for stats in type_analysis.values():
            stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] else 0
            stats["average_score"] = stats["total_score"] / stats["total"] if stats["total"] else 0

        average_score = total_score / len(model_results["question_results"]) if model_results["question_results"] else 0

        return {
            **model_results,
            "total_score": total_score,
            "average_score": average_score,
            "question_types": question_types,
            "type_analysis": type_analysis,
        }

    async def write_question_result(self, model_name, question_result):
        result_path = self.result_dir / (self.detailed_filename or f"{self._slug(model_name)}_detailed.jsonl")
        with result_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(question_result, ensure_ascii=False) + "\n")

    async def save_model_results(self, model_name, model_summary):
        summary_payload = {
            "model_id": model_summary.get("model_id"),
            "model_name": model_summary.get("model_name"),
            "total_questions": model_summary.get("total_questions"),
            "correct": model_summary.get("correct"),
            "incorrect": model_summary.get("incorrect"),
            "total_score": model_summary.get("total_score"),
            "average_score": model_summary.get("average_score"),
            "accuracy": model_summary.get("accuracy"),
            "question_types": model_summary.get("question_types"),
            "type_analysis": model_summary.get("type_analysis"),
        }
        summary_path = self.result_dir / (self.summary_filename or f"{self._slug(model_name)}_summary.json")
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(summary_payload, handle, ensure_ascii=False, indent=2)

    async def run(self):
        print(f"Starting evaluation task {self.task_id}")
        if not await self.load_dataset():
            return None

        async with ClientSession() as session:
            if not self.models:
                print("No usable models configured.")
                return None
            for model_id in self.models:
                if model_id in self.model_configs:
                    await self.test_model(model_id, session)
                else:
                    print(f"Model {model_id} is missing configuration, skipping.")

        print("Evaluation finished")
        return None

    @staticmethod
    def _slug(value: str) -> str:
        lowered = (value or "unknown").lower()
        lowered = re.sub(r"[\\/]+", "_", lowered)
        lowered = re.sub(r"\s+", "-", lowered)
        lowered = re.sub(r"[^a-z0-9._-]+", "_", lowered)
        lowered = re.sub(r"_+", "_", lowered).strip("._-")
        return lowered or "unknown"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run model evaluation on a dataset.")
    parser.add_argument("--dataset", required=True, help="Dataset JSONL path")
    parser.add_argument("--model-name", required=True, help="Model display name")
    parser.add_argument("--model-id", required=True, help="Model identifier")
    parser.add_argument("--endpoint", required=True, help="API endpoint")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--max-workers", type=int, default=3, help="Concurrent requests per model")
    args = parser.parse_args()

    MODEL_CONFIGS[args.model_id] = {
        "name": args.model_name,
        "endpoint": args.endpoint,
        "api_key": args.api_key,
    }

    evaluator = ModelEvaluator(args.dataset, [args.model_id], args.max_workers, model_configs=MODEL_CONFIGS)
    asyncio.run(evaluator.run())


if __name__ == "__main__":
    main()
