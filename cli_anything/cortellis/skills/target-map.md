# /target-map — Target Validation Report

Map the competitive landscape around a biological target.

## Usage

```
/target-map "GLP-1 receptor"
/target-map "PD-L1"
/target-map "EGFR"
```

## Workflow

### Step 1: Find the target
```bash
cortellis --json targets search --query "targetSynonyms:<TARGET>" --hits 10
```
Extract the target ID from the best match.

### Step 2: Target record
```bash
cortellis --json targets records <TARGET_ID>
```

### Step 3: Drug associations
```bash
cortellis --json targets condition-drugs <TARGET_ID>
```

### Step 4: Gene associations
```bash
cortellis --json targets condition-genes <TARGET_ID>
```

### Step 5: Interactions
```bash
cortellis --json targets interactions <TARGET_ID>
```

### Step 6: Drugs targeting this mechanism
Use NER to find the action name, then search drugs:
```bash
cortellis --json ontology search --term "<TARGET>" --category action
cortellis --json drugs search --action "<ACTION_NAME>" --phase L --hits 20
cortellis --json drugs search --action "<ACTION_NAME>" --phase C3 --hits 20
```

### Step 7: Active trials
```bash
cortellis --json trials search --query "trialActionsPrimaryInterventionsPrimary:<ACTION>" --hits 20
```

## Output Format

```
# Target Map: <Target Name>

## Target Overview
- ID: X | Name: X | Family: X
- Synonyms: X, Y, Z

## Disease Associations
| Condition | Drug Count | Highest Phase |
|-----------|-----------|---------------|

## Gene Associations
| Gene | Condition | Evidence |
|------|-----------|----------|

## Molecular Interactions
| Partner | Type | Direction |
|---------|------|-----------|

## Competitive Density
- Launched drugs: X
- Phase 3: X
- Phase 2: X
- Total pipeline: X

## Key Drugs
| Drug | Company | Phase | Indication |
|------|---------|-------|-----------|

## Active Trials
| Trial | Sponsor | Phase | Indication | Status |
|-------|---------|-------|-----------|--------|
```

## Rules
- Only report data from Cortellis.
- Target search may return multiple entries — pick the most relevant.
- If action name doesn't match exactly, try broader terms.
