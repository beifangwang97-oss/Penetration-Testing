import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from dotenv import load_dotenv
from tqdm import tqdm
from project_paths import DATASETS_REVIEWED_DIR, RESULTS_REVIEWS_DIR, ensure_standard_directories

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class OpenRouterClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, model: str, prompt: str, temperature: float = 0.2, max_retries: int = 3) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Reasoning Review",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You review cybersecurity reasoning questions for clarity, realism, and scoring consistency. "
                        "Keep the original ATT&CK target unchanged. Return only OK or valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=90)
                if response.status_code == 429:
                    time.sleep((attempt + 1) * 10)
                    continue
                response.raise_for_status()
                result = response.json()
                if result.get("choices"):
                    return result["choices"][0]["message"]["content"].strip()
                return ""
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return ""
        return ""


def load_questions(input_path: str) -> list[dict]:
    questions = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def extract_json_payload(text: str) -> dict | None:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0).strip()
    try:
        return json.loads(text)
    except Exception:
        return None


def has_bad_encoding_artifacts(text: str) -> bool:
    return any(token in (text or "") for token in ["\ufffd", "閳", "鈥", "锟"])


def is_ascii_clean(text: str) -> bool:
    try:
        (text or "").encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


SAR_SUPPORT_TERMS = ("evidence", "clue", "reasoning", "why", "based on", "support")
SAR_EVIDENCE_POINT_TERMS = (
    "evidence",
    "clue",
    "artifact",
    "command",
    "service",
    "registry",
    "traffic",
    "api",
    "snapshot",
    "memory",
    "login",
    "process",
    "script",
    "config",
    "file",
    "network",
    "session",
    "email",
    "protocol",
    "domain",
    "credential",
)


def update_msr_test_prompt(question: dict) -> str:
    blocks = []
    for step in question.get("steps", []):
        options = step.get("options", {})
        blocks.append(
            "\n".join(
                [
                    f"Step {step.get('step_id')}: {step.get('prompt', '')}",
                    f"A. {options.get('A', '')}",
                    f"B. {options.get('B', '')}",
                    f"C. {options.get('C', '')}",
                    f"D. {options.get('D', '')}",
                ]
            )
        )
    return (
        "Read the scenario and answer all steps in order.\n\n"
        f"Scenario:\n{question.get('scenario', '')}\n\n"
        + "\n\n".join(blocks)
        + "\n\nReturn only the ordered answers in compact form, for example: A,C,B"
    )


def update_sar_test_prompt(question: dict) -> str:
    return (
        f"Scenario:\n{question.get('scenario', '')}\n\n"
        f"Question:\n{question.get('question', '')}\n\n"
        "Answer in 1-4 sentences only. Name the exact MITRE ATT&CK technique or sub-technique ID, "
        "cite at least two concrete clues from the scenario, and avoid answering with only a broader parent technique."
    )


def validate_msr(question: dict) -> tuple[bool, str]:
    if question.get("question_type") != "scenario_multi_step_reasoning":
        return False, "wrong question_type"
    if not question.get("scenario") or not is_ascii_clean(question["scenario"]) or has_bad_encoding_artifacts(question["scenario"]):
        return False, "bad scenario"
    steps = question.get("steps", [])
    if len(steps) != 3:
        return False, "MSR must contain 3 steps"
    expected_focus = ["technique_identification", "next_step_prediction", "investigation_priority"]
    for idx, (step, focus) in enumerate(zip(steps, expected_focus), start=1):
        if step.get("reasoning_focus") != focus:
            return False, f"step {idx} focus mismatch"
        options = step.get("options", {})
        if set(options.keys()) != {"A", "B", "C", "D"}:
            return False, f"step {idx} options invalid"
        if step.get("correct_answer") not in {"A", "B", "C", "D"}:
            return False, f"step {idx} correct_answer invalid"
    answers = [step["correct_answer"] for step in steps]
    if question.get("correct_answer") != answers:
        return False, "correct_answer list mismatch"
    if not question.get("target_techniques"):
        return False, "missing target_techniques"
    step1_correct = steps[0]["options"][steps[0]["correct_answer"]]
    if question["target_techniques"][0] not in step1_correct:
        return False, "step 1 target mismatch"
    return True, ""


def validate_sar(question: dict) -> tuple[bool, str]:
    if question.get("question_type") != "short_answer_reasoning":
        return False, "wrong question_type"
    for field in ("scenario", "question", "reference_answer"):
        value = question.get(field, "")
        if not value or not is_ascii_clean(value) or has_bad_encoding_artifacts(value):
            return False, f"bad {field}"
    if question.get("prompt_type") != "technique_judgment":
        return False, "prompt_type must be technique_judgment"
    if not question.get("target_techniques"):
        return False, "missing target_techniques"
    question_lower = question.get("question", "").lower()
    if "exact" not in question_lower:
        return False, "question must ask for the exact ATT&CK technique or sub-technique"
    if not any(term in question_lower for term in SAR_SUPPORT_TERMS):
        return False, "question must ask for supporting evidence"
    if question["target_techniques"][0] not in question.get("reference_answer", ""):
        return False, "reference_answer missing target technique id"
    key_points = question.get("key_points", [])
    if not isinstance(key_points, list) or len(key_points) < 4:
        return False, "invalid key_points"
    key_points_lower = [str(point).lower() for point in key_points]
    if not any(question["target_techniques"][0].lower() in point for point in key_points_lower):
        return False, "key_points missing exact ATT&CK id"
    if sum(1 for point in key_points_lower if any(term in point for term in SAR_EVIDENCE_POINT_TERMS)) < 2:
        return False, "key_points need at least two evidence anchors"
    rubric = question.get("scoring_rubric", {})
    required = {"technique_correct", "evidence_used", "reasoning_clear"}
    if set(rubric.keys()) != required:
        return False, "invalid scoring_rubric keys"
    total = sum(float(v) for v in rubric.values())
    if abs(total - 1.0) > 1e-6:
        return False, "scoring_rubric must sum to 1.0"
    return True, ""


def build_msr_review_prompt(question: dict) -> str:
    return f"""Review this multi-step reasoning question.

Rules:
- Keep the same target ATT&CK IDs.
- Keep exactly 3 steps.
- Step 1 must stay technique identification.
- Step 2 must stay adversary next-step prediction.
- Step 3 must stay defender investigation priority focused on concrete evidence.
- Improve clarity and realism only.

If no changes are needed, return exactly: OK

Otherwise return JSON only with this schema:
{{
  "scenario": "...",
  "question": "...",
  "difficulty": "easy or medium or hard",
  "steps": [...],
  "overall_explanation": "...",
  "target_family": [...],
  "target_techniques": [...]
}}

Question:
{json.dumps(question, ensure_ascii=False)}"""


def build_sar_review_prompt(question: dict) -> str:
    return f"""Review this short-answer reasoning question.

Rules:
- Keep the same target ATT&CK IDs.
- Keep prompt_type as technique_judgment.
- The prompt must ask for the exact ATT&CK technique or sub-technique and the supporting evidence.
- Improve clarity, evidence grounding, exactness, and grading consistency only.
- Prefer scenarios that help distinguish the target from a broader parent technique or a close ATT&CK neighbor.
- Keep answers concise.

If no changes are needed, return exactly: OK

Otherwise return JSON only with this schema:
{{
  "scenario": "...",
  "question": "...",
  "difficulty": "easy or medium or hard",
  "reference_answer": "...",
  "key_points": ["...", "...", "..."],
  "scoring_rubric": {{"technique_correct": 0.5, "evidence_used": 0.3, "reasoning_clear": 0.2}},
  "target_family": [...],
  "target_techniques": [...]
}}

Question:
{json.dumps(question, ensure_ascii=False)}"""


def process_question(question: dict, client: OpenRouterClient, review_model: str) -> tuple[dict, str]:
    qtype = question.get("question_type", "")
    if qtype == "scenario_multi_step_reasoning":
        is_valid, reason = validate_msr(question)
        if not is_valid:
            return question, f"invalid_original: {reason}"
        prompt = build_msr_review_prompt(question)
    elif qtype == "short_answer_reasoning":
        is_valid, reason = validate_sar(question)
        if not is_valid:
            return question, f"invalid_original: {reason}"
        prompt = build_sar_review_prompt(question)
    else:
        return question, "unsupported_type"

    response = client.generate(review_model, prompt)
    if not response or response.strip() == "OK":
        return question, "unchanged"

    reviewed = extract_json_payload(response)
    if not reviewed:
        return question, "review_parse_failed"

    merged = dict(question)
    for key, value in reviewed.items():
        merged[key] = value

    if qtype == "scenario_multi_step_reasoning":
        merged["correct_answer"] = [step["correct_answer"] for step in merged.get("steps", [])]
        merged["test_prompt"] = update_msr_test_prompt(merged)
        is_valid, reason = validate_msr(merged)
    else:
        merged["prompt_type"] = "technique_judgment"
        merged["prompt"] = merged.get("question", merged.get("prompt", ""))
        merged["correct_answer"] = merged.get("reference_answer", merged.get("correct_answer", ""))
        merged["test_prompt"] = update_sar_test_prompt(merged)
        is_valid, reason = validate_sar(merged)

    if not is_valid:
        return question, f"review_invalid: {reason}"
    return merged, "modified"


def parse_args():
    parser = argparse.ArgumentParser(description="Review MSR/SAR questions")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--output-dir", default=str(DATASETS_REVIEWED_DIR))
    parser.add_argument("--max-workers", type=int, default=2)
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Missing OPENROUTER_API_KEY")
        return

    questions = load_questions(args.input)
    if not questions:
        print("No questions found")
        return

    client = OpenRouterClient(api_key)
    ensure_standard_directories()
    os.makedirs(args.output_dir, exist_ok=True)
    model_id = args.model.split("/")[-1]
    type_tag = questions[0].get("question_id", "UNK").split("-")[0]
    output_file = os.path.join(args.output_dir, f"review_{model_id}_{type_tag}_{len(questions)}.jsonl")
    summary_dir = str(RESULTS_REVIEWS_DIR / "reasoning")
    os.makedirs(summary_dir, exist_ok=True)
    summary_file = os.path.join(summary_dir, f"review_summary_{model_id}_{type_tag}_{len(questions)}.json")

    counts = {"unchanged": 0, "modified": 0, "invalid_original": 0, "review_parse_failed": 0, "review_invalid": 0, "unsupported_type": 0}

    reviewed_items = []
    file_lock = threading.Lock()
    with open(output_file, "w", encoding="utf-8") as _:
        pass
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {executor.submit(process_question, q, client, args.model): q for q in questions}
        with tqdm(total=len(questions), desc="Reviewing reasoning questions", unit="q") as progress:
            for future in as_completed(futures):
                reviewed, status = future.result()
                status_key = status.split(":", 1)[0]
                counts[status_key] = counts.get(status_key, 0) + 1
                reviewed_items.append(reviewed)
                with file_lock:
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(reviewed, ensure_ascii=False) + "\n")
                progress.update(1)

    reviewed_items.sort(key=lambda item: item.get("question_id", ""))
    with open(output_file, "w", encoding="utf-8") as f:
        for item in reviewed_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    summary = {
        "input": args.input,
        "output": output_file,
        "model": args.model,
        "counts": counts,
        "timestamp": datetime.now().isoformat(),
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
