# SSC Family Selection Strategy

## Goal

When a parent ATT&CK technique has many sub-techniques, do not generate one SSC question per sub-technique.
Instead, select a smaller number of representative sub-techniques so that:

- the family still has coverage
- the selected questions are distinguishable from each other
- the resulting SSC set remains manageable for review and evaluation

## Selection Order

For each parent technique family, choose representative sub-techniques in this order:

1. Keep the most typical sub-technique
2. Add sub-techniques that are operationally different from the first one
3. Prefer sub-techniques that lead to clearly different scenario evidence
4. Avoid selecting multiple sub-techniques that only differ in platform wording but produce nearly identical question patterns
5. If quota is limited, do not force full coverage of every niche sub-technique

## Practical Rules

### Rule 1: Keep the family anchor

Each family should keep at least one sub-technique that is the most recognizable or commonly cited representative.

Examples:

- `T1059 Command and Scripting Interpreter` should almost always keep `T1059.001 PowerShell`
- `T1218 System Binary Proxy Execution` should almost always keep `T1218.011 Rundll32`
- `T1547 Boot or Logon Autostart Execution` should almost always keep `T1547.001 Registry Run Keys / Startup Folder`

### Rule 2: Maximize evidence diversity

Prefer sub-techniques that generate different observable clues.

Good diversity examples:

- process execution path differences
- registry vs service vs scheduled execution differences
- network vs credential vs file artifact differences
- Windows vs Linux/macOS only when the evidence pattern is clearly different

### Rule 3: Prefer high-discrimination sub-techniques

A selected sub-technique should support a scenario where the answer is inferable from concrete evidence.

Prefer:

- sub-techniques with distinctive logs, artifacts, or attacker actions
- sub-techniques with strong ATT&CK-style wording

Avoid prioritizing:

- sub-techniques whose scenarios collapse back into the parent technique
- sub-techniques that are too abstract and hard to distinguish in SSC format

### Rule 4: Avoid near-duplicates in the same family

If two sub-techniques would produce nearly the same scenario template, keep only one unless the family quota is large.

### Rule 5: Use the parent technique itself when needed

If a family contains many niche sub-techniques and the quota is small, one of the allocated questions may target the parent technique directly.
This is useful when:

- the family is broad
- no single sub-technique should dominate
- a mixed scenario better reflects the family than a narrow sub-technique

## Recommended Family Coverage Pattern

### Quota = 1

- Choose the most typical or highest-discrimination sub-technique
- If all sub-techniques are too niche, use the parent technique

### Quota = 2

- Choose one anchor sub-technique
- Choose one operationally different sub-technique

### Quota = 3

- Choose one anchor sub-technique
- Choose one different artifact pattern
- Choose one different platform or execution path

### Quota = 4

- Choose one anchor sub-technique
- Choose two strongly different operational variants
- Use the fourth slot for either another high-value sub-technique or the parent-level mixed scenario

### Quota = 5

- Cover the family with broad internal diversity
- Include at least one parent-level or family-level scenario if the family is very fragmented

## Examples

### `T1059 Command and Scripting Interpreter`

If quota is 4, a strong first-pass set is:

- `T1059.001 PowerShell`
- `T1059.003 Windows Command Shell`
- `T1059.004 Unix Shell`
- `T1059.009 Cloud API`

Reason:

- recognizable anchor
- Windows and Unix command execution are distinct
- Cloud API creates a very different scenario pattern

### `T1546 Event Triggered Execution`

If quota is 5, a strong first-pass set should cover clearly different trigger patterns, such as:

- WMI-based trigger
- IFEO-based trigger
- PowerShell profile trigger
- Unix shell configuration trigger
- one parent-level mixed trigger scenario

### `T1036 Masquerading`

If quota is 4, prefer variants with different observable deception styles, such as:

- right-to-left override
- double file extension
- rename legitimate utilities
- masquerade task or service

## Output Expectations For Generator Refactor

The generator should eventually support:

- family quota input per parent technique
- representative target list per family
- optional parent-level scenario slots
- related sub-techniques appearing as context, not necessarily as the primary answer
