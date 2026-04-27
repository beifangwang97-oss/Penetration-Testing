# Schema And Directory Normalization Design

## Scope

Normalize the project around a single dataset schema and a single directory layout without rewriting the full evaluation logic.

## Decisions

1. Use `question_form` as the canonical field for question form.
2. Use `capability_dimension` as the canonical field for assessment dimension.
3. Keep `question_type` as a legacy compatibility field because existing scripts and historical datasets still reference it.
4. Treat `data/processed`, `datasets/generated`, `datasets/reviewed`, `datasets/final`, `results/evaluations`, `results/reviews`, and `results/analysis` as the standard layout.
5. Keep legacy directories readable during transition, but move all default outputs to the standard layout.

## Expected impact

- New datasets become structurally consistent.
- Evaluation summaries can separate question form from capability dimension.
- The web console can scan standardized dataset locations first.
- Historical files remain usable during the migration window.
