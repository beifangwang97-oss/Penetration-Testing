QUESTION_FORM_BY_PREFIX = {
    "SC": "single_choice",
    "SSC": "scenario_single_choice",
    "MC": "multiple_choice",
    "JU": "judgment",
    "SQ": "sequencing",
    "MSR": "scenario_multi_step_reasoning",
    "SAR": "short_answer_reasoning",
}

LEGACY_CATEGORY_TO_DIMENSION = {
    "technique_purpose": "technique_purpose",
    "tactic_classification": "tactic_classification",
    "tool_mapping": "tool_mapping",
    "defense_detection": "defense_detection",
    "attack_scenario": "attack_scenario",
    "技术关联分析": "technique_association_analysis",
    "跨战术关联分析": "cross_tactic_correlation_analysis",
    "scenario_single_choice": "scenario_technique_identification",
    "scenario_multi_step_reasoning": "multi_step_reasoning",
    "short_answer_reasoning": "short_answer_technique_judgment",
}


def question_form_from_id(question_id: str) -> str:
    prefix = (question_id or "").split("-", 1)[0]
    return QUESTION_FORM_BY_PREFIX.get(prefix, "unknown")


def resolve_question_form(question: dict) -> str:
    question_form = question.get("question_form")
    if question_form:
        return question_form

    legacy_type = question.get("question_type")
    if legacy_type in set(QUESTION_FORM_BY_PREFIX.values()):
        return legacy_type

    return question_form_from_id(question.get("question_id", ""))


def resolve_capability_dimension(question: dict) -> str:
    capability_dimension = question.get("capability_dimension")
    if capability_dimension:
        return capability_dimension

    legacy_type = question.get("question_type")
    if legacy_type in LEGACY_CATEGORY_TO_DIMENSION:
        return LEGACY_CATEGORY_TO_DIMENSION[legacy_type]

    question_form = resolve_question_form(question)
    defaults = {
        "single_choice": "general_single_choice",
        "scenario_single_choice": "scenario_technique_identification",
        "multiple_choice": "technique_association_analysis",
        "judgment": "fact_verification",
        "sequencing": "procedure_ordering",
        "scenario_multi_step_reasoning": "multi_step_reasoning",
        "short_answer_reasoning": "short_answer_technique_judgment",
    }
    return defaults.get(question_form, "unknown")
