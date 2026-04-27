import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from dotenv import load_dotenv
from tqdm import tqdm

from attack_id_aliases import canonicalize_attack_id, canonicalize_attack_ids
from project_paths import RESULTS_EVALUATIONS_DIR, ensure_standard_directories

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_attack_id_name_map() -> dict[str, str]:
    attack_path = os.path.join("data", "attack_data.json")
    if not os.path.exists(attack_path):
        return {}
    with open(attack_path, "r", encoding="utf-8") as f:
        attack_data = json.load(f)
    lookup = {}
    for tactic in attack_data.get("tactics", []):
        for technique in tactic.get("techniques", []):
            if technique.get("id") and technique.get("name"):
                lookup[technique["id"]] = technique["name"]
            for sub in technique.get("sub_techniques", []):
                if sub.get("id") and sub.get("name"):
                    lookup[sub["id"]] = sub["name"]
    return lookup


ATTACK_ID_NAME_MAP = load_attack_id_name_map()


class OpenRouterClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, model: str, prompt: str, system_prompt: str, temperature: float = 0.1, max_retries: int = 3) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Reasoning Evaluation",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
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


def extract_choice_sequence(text: str) -> list[str]:
    return re.findall(r"[A-D]", (text or "").upper())


def extract_attack_ids(text: str) -> list[str]:
    return re.findall(r"T\d{4}(?:\.\d{3})?", text or "")


def tokenize(text: str) -> set[str]:
    normalized = re.sub(r"[^A-Za-z0-9\.]+", " ", (text or "").lower())
    return {token for token in normalized.split() if len(token) >= 3}


def token_overlap_score(source: str, answer_tokens: set[str]) -> float:
    source_tokens = tokenize(source)
    if not source_tokens:
        return 0.0
    return len(source_tokens & answer_tokens) / len(source_tokens)


def technique_match_score(question: dict, model_answer: str) -> float:
    target_ids = canonicalize_attack_ids(question.get("target_techniques", []))
    if not target_ids:
        return 0.0
    target_id = target_ids[0]
    parent_id = target_id.split(".")[0]
    answer_ids = set(canonicalize_attack_ids(extract_attack_ids(model_answer)))
    if target_id in answer_ids:
        return 1.0
    if parent_id in answer_ids:
        return 0.35

    answer_tokens = tokenize(model_answer)
    target_name = ATTACK_ID_NAME_MAP.get(target_id, "").lower()
    parent_name = ATTACK_ID_NAME_MAP.get(parent_id, "").lower()
    if target_name and token_overlap_score(target_name, answer_tokens) >= 0.6:
        return 1.0
    if parent_name and token_overlap_score(parent_name, answer_tokens) >= 0.6:
        return 0.35
    return 0.0


def score_msr(question: dict, model_answer: str) -> dict:
    expected = [str(item).upper() for item in question.get("correct_answer", [])]
    predicted = extract_choice_sequence(model_answer)[: len(expected)]
    matched = sum(1 for p, e in zip(predicted, expected) if p == e)
    step_accuracy = matched / len(expected) if expected else 0.0
    return {
        "predicted_answers": predicted,
        "expected_answers": expected,
        "strict_correct": predicted == expected,
        "score": step_accuracy,
        "score_breakdown": {
            "step_accuracy": step_accuracy,
            "full_match": 1.0 if predicted == expected else 0.0,
        },
    }


def build_sar_judge_prompt(question: dict, model_answer: str, rule_score: float, rule_breakdown: dict) -> str:
    return f"""Score the model answer for this short-answer ATT&CK reasoning question.

Rules:
- Score each rubric field from 0.0 to 1.0.
- Be strict.
- Use the scenario and reference answer as ground truth.
- Return JSON only.

Question:
{json.dumps(question, ensure_ascii=False)}

Model answer:
{model_answer}

Precomputed rule score:
{rule_score}

Precomputed rule breakdown:
{json.dumps(rule_breakdown, ensure_ascii=False)}

Return:
{{
  "technique_correct": 0.0,
  "evidence_used": 0.0,
  "reasoning_clear": 0.0,
  "judge_score": 0.0,
  "verdict": "correct or partially_correct or incorrect",
  "comment": "short explanation"
}}"""


def parse_json_response(text: str) -> dict | None:
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


def score_sar(question: dict, model_answer: str, client: OpenRouterClient, judge_model: str) -> dict:
    id_hit = technique_match_score(question, model_answer)

    key_points = question.get("key_points", [])
    answer_tokens = tokenize(model_answer)
    point_hits = 0
    for point in key_points:
        point_tokens = tokenize(point)
        if point_tokens and len(point_tokens & answer_tokens) / len(point_tokens) >= 0.4:
            point_hits += 1
    evidence_hit = point_hits / len(key_points) if key_points else 0.0

    sentence_count = len([part for part in re.split(r"[.!?]+", model_answer or "") if part.strip()])
    format_relevance = 1.0 if model_answer and sentence_count <= 4 else 0.5

    target_id = canonicalize_attack_id((question.get("target_techniques") or [""])[0])
    parent_id = target_id.split(".")[0] if target_id else ""
    exactness_hit = 1.0
    answer_ids = set(canonicalize_attack_ids(extract_attack_ids(model_answer)))
    if target_id and target_id != parent_id and target_id not in answer_ids:
        if parent_id in answer_ids:
            exactness_hit = 0.0
        else:
            lower_answer = (model_answer or "").lower()
            if ATTACK_ID_NAME_MAP.get(parent_id, "").lower() and ATTACK_ID_NAME_MAP.get(parent_id, "").lower() in lower_answer:
                exactness_hit = 0.0

    rule_score = 0.45 * id_hit + 0.25 * evidence_hit + 0.15 * format_relevance + 0.15 * exactness_hit
    rule_breakdown = {
        "technique_match": id_hit,
        "key_point_coverage": evidence_hit,
        "format_relevance": format_relevance,
        "exactness": exactness_hit,
    }

    judge_prompt = build_sar_judge_prompt(question, model_answer, rule_score, rule_breakdown)
    judge_response = client.generate(
        judge_model,
        judge_prompt,
        "You are a strict grader for cybersecurity short-answer questions. Return JSON only.",
    )
    judge_json = parse_json_response(judge_response) or {
        "technique_correct": 0.0,
        "evidence_used": 0.0,
        "reasoning_clear": 0.0,
        "judge_score": 0.0,
        "verdict": "incorrect",
        "comment": "judge_parse_failed",
    }

    judge_score = float(judge_json.get("judge_score", 0.0))
    final_score = 0.6 * rule_score + 0.4 * judge_score
    return {
        "strict_correct": final_score >= 0.7,
        "score": final_score,
        "score_breakdown": {
            "rule_score": rule_score,
            "rule_breakdown": rule_breakdown,
            "judge_score": judge_score,
            "judge_breakdown": {
                "technique_correct": judge_json.get("technique_correct", 0.0),
                "evidence_used": judge_json.get("evidence_used", 0.0),
                "reasoning_clear": judge_json.get("reasoning_clear", 0.0),
                "verdict": judge_json.get("verdict", "incorrect"),
                "comment": judge_json.get("comment", ""),
            },
        },
    }


def process_question(question: dict, answer_client: OpenRouterClient, answer_model: str, judge_model: str) -> dict:
    model_answer = answer_client.generate(
        answer_model,
        question.get("test_prompt", ""),
        "You answer cybersecurity questions as accurately and concisely as possible.",
    )

    qtype = question.get("question_type", "")
    if qtype == "scenario_multi_step_reasoning":
        scoring = score_msr(question, model_answer)
    elif qtype == "short_answer_reasoning":
        scoring = score_sar(question, model_answer, answer_client, judge_model)
    else:
        scoring = {
            "strict_correct": False,
            "score": 0.0,
            "score_breakdown": {"error": "unsupported question_type"},
        }

    return {
        "question_id": question.get("question_id", ""),
        "question_type": qtype,
        "model_answer": model_answer,
        "correct_answer": question.get("correct_answer"),
        "strict_correct": scoring["strict_correct"],
        "score": scoring["score"],
        "score_breakdown": scoring["score_breakdown"],
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate MSR/SAR questions with strict and judge-based scoring")
    parser.add_argument("--input", required=True)
    parser.add_argument("--answer-model", default="openai/gpt-4o-mini")
    parser.add_argument("--judge-model", default="openai/gpt-4o-mini")
    parser.add_argument("--output-dir", default=str(RESULTS_EVALUATIONS_DIR))
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
    answer_tag = args.answer_model.split("/")[-1]
    judge_tag = args.judge_model.split("/")[-1]
    dataset_tag = questions[0].get("question_id", "UNK").split("-")[0]
    output_file = os.path.join(args.output_dir, f"eval_{dataset_tag}_{answer_tag}_judge_{judge_tag}_{len(questions)}.jsonl")
    summary_file = os.path.join(args.output_dir, f"eval_summary_{dataset_tag}_{answer_tag}_judge_{judge_tag}_{len(questions)}.json")

    results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(process_question, q, client, args.answer_model, args.judge_model): q
            for q in questions
        }
        with tqdm(total=len(questions), desc="Evaluating reasoning questions", unit="q") as progress:
            for future in as_completed(futures):
                results.append(future.result())
                progress.update(1)

    results.sort(key=lambda item: item.get("question_id", ""))
    with open(output_file, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    total = len(results)
    avg_score = sum(item.get("score", 0.0) for item in results) / total if total else 0.0
    strict_correct = sum(1 for item in results if item.get("strict_correct"))
    by_type = {}
    for item in results:
        qtype = item.get("question_type", "unknown")
        by_type.setdefault(qtype, {"count": 0, "avg_score": 0.0, "strict_correct": 0})
        by_type[qtype]["count"] += 1
        by_type[qtype]["avg_score"] += item.get("score", 0.0)
        by_type[qtype]["strict_correct"] += 1 if item.get("strict_correct") else 0
    for qtype, stats in by_type.items():
        stats["avg_score"] = stats["avg_score"] / stats["count"] if stats["count"] else 0.0

    summary = {
        "input": args.input,
        "output": output_file,
        "answer_model": args.answer_model,
        "judge_model": args.judge_model,
        "total_questions": total,
        "average_score": avg_score,
        "strict_correct_count": strict_correct,
        "strict_accuracy": strict_correct / total if total else 0.0,
        "by_type": by_type,
        "timestamp": datetime.now().isoformat(),
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
