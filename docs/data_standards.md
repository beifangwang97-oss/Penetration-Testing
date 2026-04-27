# Data Standards

## Unified question fields

All formal datasets should now use:

- `question_form`: canonical question form
- `capability_dimension`: canonical assessment dimension
- `question_type`: legacy compatibility field only

Supported `question_form` values:

- `single_choice`
- `multiple_choice`
- `judgment`
- `sequencing`
- `scenario_single_choice`
- `scenario_multi_step_reasoning`
- `short_answer_reasoning`

Recommended `capability_dimension` values currently used in the project:

- `technique_purpose`
- `tactic_classification`
- `tool_mapping`
- `defense_detection`
- `attack_scenario`
- `technique_association_analysis`
- `cross_tactic_correlation_analysis`
- `scenario_technique_identification`
- `multi_step_reasoning`
- `short_answer_technique_judgment`
- `fact_verification`
- `procedure_ordering`

## Directory standard

The project now treats the following directories as the standard layout:

```text
demo/
  data/
    raw/
    processed/
  datasets/
    generated/
    reviewed/
    final/
  results/
    evaluations/
    reviews/
    analysis/
  uploads/
```

Meaning:

- `data/raw/`: raw or imported ATT&CK source data
- `data/processed/`: parsed ATT&CK cache used by scripts
- `datasets/generated/`: generated but not yet reviewed question sets
- `datasets/reviewed/`: reviewed question sets
- `datasets/final/`: frozen formal evaluation datasets
- `results/evaluations/`: model evaluation outputs
- `results/reviews/`: review summaries and logs
- `results/analysis/`: comparison reports, charts, dataset quality reports
- `uploads/`: temporary user uploads from the web console

## Transition rule

Legacy directories such as `output/`, `review_output/`, `evaluation_output/`, and `data/attack_data.json` are only kept for migration compatibility. All new generation, review, freezing, evaluation, and analysis work should write into the standard layout above.

Reasoning question types are no longer stored under separate subtype folders. MSR and SAR files should be placed directly under:

- `datasets/generated/`
- `datasets/reviewed/`
- `datasets/final/`
- `results/evaluations/`
