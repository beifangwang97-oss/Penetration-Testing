import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

from generate_scenario_single_choice import build_generation_tasks, load_attack_data

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

    def generate(self, model: str, prompt: str, temperature: float = 0.4, max_retries: int = 3) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Short Answer Reasoning Generator",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate high-quality MITRE ATT&CK short-answer cybersecurity reasoning questions. "
                        "Return only valid JSON and follow the requested schema exactly."
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
                    return {"content": result["choices"][0]["message"]["content"], "error": None}
                return {"content": "", "error": "No choices in response"}
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"content": "", "error": str(exc)}
        return {"content": "", "error": "Max retries exceeded"}


def load_prompt_template() -> str:
    with open("config/prompt_templates.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("short_answer_reasoning", "")


def extract_json_payload(content: str) -> str:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        return match.group(0).strip()
    return content.strip()


def build_test_prompt(question_data: dict) -> str:
    return (
        f"Scenario:\n{question_data.get('scenario', '')}\n\n"
        f"Question:\n{question_data.get('prompt', '')}\n\n"
        "Answer in 1-4 sentences only. Name the exact MITRE ATT&CK technique or sub-technique ID, "
        "cite at least two concrete clues from the scenario, and avoid answering with only a broader parent technique."
    )


def has_bad_encoding_artifacts(text: str) -> bool:
    return any(token in (text or "") for token in ["\ufffd", "閳", "鈥", "锟"])


def is_ascii_clean(text: str) -> bool:
    try:
        (text or "").encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


SUPPORT_TERMS = ("evidence", "clue", "reasoning", "why", "based on", "support")
REFERENCE_EVIDENCE_TERMS = ("because", "evidence", "clue", "indicates", "shows", "reveals", "observed", "based on", "since")
EVIDENCE_POINT_TERMS = (
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
PRECISION_TERMS = ("exact", "precise", "broader", "parent", "adjacent", "specific")


def validate_question_data(data: dict, expected_target_id: str, expected_family_id: str) -> tuple[bool, str]:
    if not data.get("title"):
        return False, "missing title"
    if not data.get("scenario") or len(data["scenario"].strip()) < 60:
        return False, "scenario too short"
    if has_bad_encoding_artifacts(data.get("scenario", "")) or not is_ascii_clean(data.get("scenario", "")):
        return False, "scenario contains encoding artifacts"
    if data.get("prompt_type") != "technique_judgment":
        return False, "prompt_type must be technique_judgment"
    if not data.get("prompt"):
        return False, "missing prompt"
    if has_bad_encoding_artifacts(data.get("prompt", "")) or not is_ascii_clean(data.get("prompt", "")):
        return False, "prompt contains encoding artifacts"
    prompt_lower = data["prompt"].lower()
    if "technique" not in prompt_lower and "att&ck" not in prompt_lower:
        return False, "prompt must explicitly ask for the technique"
    if "exact" not in prompt_lower:
        return False, "prompt must require the exact ATT&CK identification"
    if not any(term in prompt_lower for term in SUPPORT_TERMS):
        return False, "prompt must ask for supporting evidence"
    if data.get("difficulty") not in {"easy", "medium", "hard"}:
        return False, "invalid difficulty"
    if expected_family_id not in data.get("target_family", []):
        return False, "target_family missing expected id"
    if expected_target_id not in data.get("target_techniques", []):
        return False, "target_techniques missing expected id"
    if not data.get("reference_answer"):
        return False, "missing reference_answer"
    if has_bad_encoding_artifacts(data.get("reference_answer", "")) or not is_ascii_clean(data.get("reference_answer", "")):
        return False, "reference_answer contains encoding artifacts"
    if expected_target_id not in data["reference_answer"]:
        return False, "reference_answer must include expected ATT&CK id"
    reference_lower = data["reference_answer"].lower()
    if not any(term in reference_lower for term in REFERENCE_EVIDENCE_TERMS):
        return False, "reference_answer must explain supporting evidence"
    key_points = data.get("key_points", [])
    if not isinstance(key_points, list) or not 4 <= len(key_points) <= 5:
        return False, "key_points must contain 4-5 items"
    if any(not is_ascii_clean(point) or has_bad_encoding_artifacts(point) for point in key_points):
        return False, "key_points contain encoding artifacts"
    key_points_lower = [point.lower() for point in key_points]
    if not any(expected_target_id.lower() in point for point in key_points_lower):
        return False, "key_points must include the exact ATT&CK id"
    if sum(1 for point in key_points_lower if any(term in point for term in EVIDENCE_POINT_TERMS)) < 2:
        return False, "key_points must include at least two concrete evidence points"
    if not any(term in " ".join(key_points_lower) for term in PRECISION_TERMS):
        return False, "key_points must include precision guidance"
    rubric = data.get("scoring_rubric", {})
    if set(rubric.keys()) != {"technique_correct", "evidence_used", "reasoning_clear"}:
        return False, "invalid scoring_rubric keys"
    total = sum(float(value) for value in rubric.values())
    if abs(total - 1.0) > 1e-6:
        return False, "scoring_rubric must sum to 1.0"
    return True, ""


def generate_question(
    client: OpenRouterClient,
    template: str,
    tactic: dict,
    technique: dict,
    sub_technique: dict,
    question_index: int,
    model_name: str,
):
    target_id = sub_technique.get("id", technique["id"])
    prompt = template.format(
        tactic_id=tactic["id"],
        tactic_name=tactic.get("name", ""),
        tactic_description=tactic.get("description", "").replace("\n", " ").strip()[:300],
        technique_id=technique["id"],
        technique_name=technique.get("name", ""),
        technique_description=technique.get("description", "").replace("\n", " ").strip()[:500],
        sub_technique_id=target_id,
        sub_technique_name=sub_technique.get("name", technique.get("name", "")),
    )

    result = client.generate(model=model_name, prompt=prompt)
    if result.get("error"):
        print(f"  generation error: {result['error']}")
        return None

    json_str = extract_json_payload(result["content"])
    for attempt in range(3):
        try:
            data = json.loads(json_str)
            is_valid, reason = validate_question_data(data, target_id, technique["id"])
            if not is_valid:
                print(f"  validation failed: {reason}")
                return None

            normalized = {
                "question_id": f"SAR-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{target_id}",
                "question_type": "short_answer_reasoning",
                "difficulty": data["difficulty"],
                "title": data["title"],
                "scenario": data["scenario"],
                "prompt_type": data["prompt_type"],
                "question": data["prompt"],
                "prompt": data["prompt"],
                "correct_answer": data["reference_answer"],
                "reference_answer": data["reference_answer"],
                "key_points": data["key_points"],
                "scoring_rubric": data["scoring_rubric"],
                "target_family": data["target_family"],
                "target_techniques": data["target_techniques"],
            }
            normalized["test_prompt"] = build_test_prompt(normalized)
            return normalized
        except json.JSONDecodeError:
            if attempt < 2:
                json_str = json_str.replace("\n", " ").replace("\r", " ")
                json_str = re.sub(r",\s*}", "}", json_str)
                json_str = re.sub(r",\s*\]", "]", json_str)
                continue
            return None
    return None


def parse_args():
    parser = argparse.ArgumentParser(description="Generate short answer reasoning questions")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--model-id", default="gpt-4o-mini")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--output-file", default="")
    parser.add_argument("--output-dir", default="output/reasoning/sar")
    parser.add_argument("--task-mode", choices=["family", "full"], default="family")
    return parser.parse_args()


def main():
    args = parse_args()
    attack_data = load_attack_data()
    prompt_template = load_prompt_template()
    if not attack_data or not prompt_template:
        return

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Missing OPENROUTER_API_KEY")
        return

    client = OpenRouterClient(api_key)
    tasks = build_generation_tasks(
        attack_data,
        shuffle=not args.no_shuffle,
        seed=args.seed,
        task_mode=args.task_mode,
    )
    if args.limit > 0:
        tasks = tasks[: args.limit]

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    output_file = args.output_file or f"{output_dir}/{args.model_id}_sar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    total_generated = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {
            executor.submit(
                generate_question,
                client,
                prompt_template,
                tactic,
                technique,
                sub_technique,
                index,
                args.model,
            ): (technique, sub_technique)
            for tactic, technique, sub_technique, index in tasks
        }

        with tqdm(total=len(tasks), desc="Generating SAR", unit="q") as progress:
            for future in as_completed(future_map):
                technique, sub_technique = future_map[future]
                try:
                    question = future.result()
                    if question:
                        with open(output_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(question, ensure_ascii=False) + "\n")
                        total_generated += 1
                    else:
                        print(f"FAIL {sub_technique.get('id', technique.get('id', ''))}")
                except Exception as exc:
                    print(f"ERROR {sub_technique.get('id', technique.get('id', ''))}: {exc}")
                progress.update(1)

    print(f"Generated {total_generated} questions")
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
