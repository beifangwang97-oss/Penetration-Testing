# Frontend Redesign Design

## Goal

Refit the evaluation console into a concise academic dashboard for formal experiments. The page should remove non-evaluation noise, prioritize result readability, and support multi-model comparison across overall, question-type, and capability-like dimensions.

## Approved Direction

- Layout: compact control band on top, analysis workspace below
- Visual style: light academic panel, restrained, professional
- Result logic: overview first, then dimensional breakdown, then diagnosis, then detailed samples
- Comparison strategy: multi-model comparison is the default, not single-model spotlighting

## Information Architecture

### 1. Header

- Platform title
- Short subtitle focused on evaluation usage
- Small status chip only

### 2. Control Band

- Dataset selection, upload, and deletion
- Model selection and custom model addition
- Run summary and evaluation trigger
- Progress status shown in a compact side panel

### 3. Results Workspace

- Overview KPIs
- Model ranking table
- Overall score comparison chart
- Question-type comparison chart
- Type-analysis comparison matrix
- Balance radar for leading models
- Diagnostic cards for strongest and weakest dimensions
- Detailed sample table with model filter

## Data Handling

- Reuse existing `/api/datasets`, `/api/models`, `/api/start`, `/api/progress`, and `/api/results`
- Normalize result objects client-side to support sparse question-type and type-analysis keys across models
- If backend fields are insufficient, extend backend result payloads without changing the main workflow

## Visual Rules

- Remove hero, marketing copy, help/about modal clutter, decorative chips, and noisy workflow text
- Use light backgrounds, fine borders, muted neutrals, and restrained blue accents
- Keep model colors stable across all charts
- Use tables, grouped bars, and matrices before decorative visual forms

## Validation

- Verify dataset upload, dataset selection, model selection, evaluation start, progress polling, and result rendering
- Verify charts render with one model and multiple models
- Verify the page remains readable for long model names and long dataset paths
