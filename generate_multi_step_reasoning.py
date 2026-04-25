import argparse
import json
import os
import random
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

    def generate(self, model: str, prompt: str, temperature: float = 0.5, max_retries: int = 3) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Athena-Software-Group/athenabench",
            "X-Title": "ATT&CK Multi-Step Reasoning Generator",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate high-quality MITRE ATT&CK cybersecurity reasoning questions. "
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
    return config.get("scenario_multi_step_reasoning", "")


def extract_json_payload(content: str) -> str:
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        return match.group(0).strip()
    return content.strip()


def extract_attack_ids(text: str) -> list[str]:
    return re.findall(r"T\d{4}(?:\.\d{3})?", text or "")


def load_attack_id_name_map() -> dict[str, str]:
    with open("data/attack_data.json", "r", encoding="utf-8") as f:
        attack_data = json.load(f)

    lookup = {}
    for tactic in attack_data.get("tactics", []):
        for technique in tactic.get("techniques", []):
            if technique.get("id") and technique.get("name"):
                lookup[technique["id"]] = technique["name"].strip()
            for sub in technique.get("sub_techniques", []):
                if sub.get("id") and sub.get("name"):
                    lookup[sub["id"]] = sub["name"].strip()
    return lookup


ATTACK_ID_NAME_MAP = load_attack_id_name_map()


def build_test_prompt(question_data: dict) -> str:
    step_blocks = []
    for step in question_data.get("steps", []):
        options = step.get("options", {})
        step_blocks.append(
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
        f"Scenario:\n{question_data.get('scenario', '')}\n\n"
        + "\n\n".join(step_blocks)
        + "\n\nReturn only the ordered answers in compact form, for example: A,C,B"
    )


def has_bad_encoding_artifacts(text: str) -> bool:
    return any(token in (text or "") for token in ["\ufffd", "閳", "鈥", "锟"])


def is_ascii_clean(text: str) -> bool:
    try:
        (text or "").encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def validate_steps(steps: list, expected_target_id: str) -> tuple[bool, str]:
    if not isinstance(steps, list) or len(steps) != 3:
        return False, "steps must contain exactly 3 items"

    seen_ids = set()
    focus_allowed = {
        "technique_identification",
        "stage_inference",
        "next_step_prediction",
        "investigation_priority",
        "response_decision",
    }

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            return False, f"step {index} is not an object"
        if step.get("step_id") in seen_ids:
            return False, f"duplicate step_id {step.get('step_id')}"
        seen_ids.add(step.get("step_id"))

        if not step.get("prompt"):
            return False, f"step {index} missing prompt"
        if (
            has_bad_encoding_artifacts(step.get("prompt", ""))
            or has_bad_encoding_artifacts(step.get("step_explanation", ""))
            or not is_ascii_clean(step.get("prompt", ""))
            or not is_ascii_clean(step.get("step_explanation", ""))
        ):
            return False, f"step {index} contains encoding artifacts"
        if step.get("reasoning_focus") not in focus_allowed:
            return False, f"step {index} invalid reasoning_focus"
        options = step.get("options", {})
        if set(options.keys()) != {"A", "B", "C", "D"}:
            return False, f"step {index} options must be A-D"
        if step.get("correct_answer") not in {"A", "B", "C", "D"}:
            return False, f"step {index} invalid correct_answer"
        if not step.get("step_explanation"):
            return False, f"step {index} missing step_explanation"

    first_step = steps[0]
    if first_step.get("reasoning_focus") != "technique_identification":
        return False, "step 1 must be technique_identification"
    if steps[1].get("reasoning_focus") != "next_step_prediction":
        return False, "step 2 must be next_step_prediction"
    if steps[2].get("reasoning_focus") != "investigation_priority":
        return False, "step 3 must be investigation_priority"

    step1_options = first_step.get("options", {})
    correct_option_text = step1_options.get(first_step.get("correct_answer", ""), "")
    correct_ids = extract_attack_ids(correct_option_text)
    if len(correct_ids) != 1 or correct_ids[0] != expected_target_id:
        return False, "step 1 correct option must map to target ATT&CK id"

    seen_attack_ids = set()
    for label in ("A", "B", "C", "D"):
        ids = extract_attack_ids(step1_options.get(label, ""))
        if len(ids) != 1:
            return False, "step 1 options must each contain exactly one ATT&CK id"
        attack_id = ids[0]
        if attack_id in seen_attack_ids:
            return False, "step 1 options must use distinct ATT&CK ids"
        seen_attack_ids.add(attack_id)
    for step in steps[1:]:
        for label in ("A", "B", "C", "D"):
            if extract_attack_ids(step.get("options", {}).get(label, "")):
                return False, "steps after step 1 must not include ATT&CK ids in options"

    step2_bad_keywords = {
        "review",
        "investigate",
        "analyze",
        "monitor",
        "update",
        "isolate",
        "notify",
        "check",
        "restore",
    }
    step2_prompt = steps[1].get("prompt", "").lower()
    if "security team" in step2_prompt or "defender" in step2_prompt or "analyst" in step2_prompt:
        return False, "step 2 should ask for adversary next action, not defender action"
    step2_correct = steps[1].get("options", {}).get(steps[1].get("correct_answer", ""), "").lower()
    if any(keyword in step2_correct for keyword in step2_bad_keywords):
        return False, "step 2 correct answer is too defender-oriented"

    evidence_keywords = {
        "log",
        "logs",
        "task",
        "tasks",
        "registry",
        "run key",
        "binary",
        "file",
        "script",
        "process",
        "command",
        "event",
        "traffic",
        "connection",
        "account",
        "firmware",
        "boot",
        "artifact",
        "service",
        "domain",
        "dns",
        "proxy",
        "lsass",
    }
    step3_correct = steps[2].get("options", {}).get(steps[2].get("correct_answer", ""), "").lower()
    if not any(keyword in step3_correct for keyword in evidence_keywords):
        return False, "step 3 correct answer must reference a concrete evidence source"

    return True, ""


def validate_question_data(data: dict, expected_target_id: str, expected_family_id: str) -> tuple[bool, str]:
    if not data.get("title"):
        return False, "missing title"
    if not data.get("scenario") or len(data["scenario"].strip()) < 80:
        return False, "scenario too short"
    if (
        has_bad_encoding_artifacts(data.get("scenario", ""))
        or has_bad_encoding_artifacts(data.get("overall_explanation", ""))
        or not is_ascii_clean(data.get("scenario", ""))
        or not is_ascii_clean(data.get("overall_explanation", ""))
    ):
        return False, "question contains encoding artifacts"
    if not data.get("question"):
        return False, "missing question overview"
    if not data.get("overall_explanation"):
        return False, "missing overall_explanation"
    if data.get("difficulty") not in {"easy", "medium", "hard"}:
        return False, "invalid difficulty"

    target_family = data.get("target_family", [])
    target_techniques = data.get("target_techniques", [])
    if not isinstance(target_family, list) or expected_family_id not in target_family:
        return False, "target_family missing expected technique id"
    if not isinstance(target_techniques, list) or expected_target_id not in target_techniques:
        return False, "target_techniques missing expected target id"

    return validate_steps(data.get("steps", []), expected_target_id)


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
                "question_id": f"MSR-{question_index:03d}",
                "tactic_technique": f"{tactic.get('id', '')}-{technique.get('id', '')}-{target_id}",
                "question_type": "scenario_multi_step_reasoning",
                "difficulty": data["difficulty"],
                "title": data["title"],
                "scenario": data["scenario"],
                "question": data["question"],
                "steps": data["steps"],
                "correct_answer": [step["correct_answer"] for step in data["steps"]],
                "overall_explanation": data["overall_explanation"],
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
    parser = argparse.ArgumentParser(description="Generate scenario multi-step reasoning questions")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--model-id", default="gpt-4o-mini")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--output-file", default="")
    parser.add_argument("--output-dir", default="output/reasoning/msr")
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
    output_file = args.output_file or f"{output_dir}/{args.model_id}_msr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

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

        with tqdm(total=len(tasks), desc="Generating MSR", unit="q") as progress:
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
