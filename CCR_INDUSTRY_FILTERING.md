# CCR Industry Filtering

The CCR industry filter is a deterministic metadata tagger for normalized CCR acquisition
records. It is intended as a first-pass triage tool for narrowing large CCR runs to
high-value domains before deeper conversion and legal extraction.

## Inputs And Outputs

Input:

- `02_Regulations_CCR/_dataset/ccr_items.jsonl`

Outputs:

- `02_Regulations_CCR/_dataset/ccr_items_tagged.jsonl`
- `02_Regulations_CCR/_dataset/ccr_items_tagged.csv`
- `02_Regulations_CCR/_dataset/ccr_tag_summary.json`
- Optional filtered JSONL/CSV plus a filter summary when include/exclude filters are used.

The CCR bulk runner writes the normalized dataset and full tagged dataset at the end of
each run by default. Use `--no-industry-tags` on `geode-ccr-bulk` only when you want to
skip this post-processing step. If the normalized dataset is missing, the standalone
filter CLI first rebuilds it from CCR acquisition artifacts by calling the CCR dataset
writer.

## Taxonomy

The editable taxonomy lives in:

`geode/connectors/ccr_industry_taxonomy.py`

Rules are intentionally conservative and explainable. Each rule declares:

- `source`: `agency`, `keyword`, or `citation`
- metadata fields to inspect
- substring terms and/or CCR citation prefixes
- industry tags from the Geode ontology
- topic tags from the Geode subject ontology
- CCR filter-specific domain tags
- confidence and human-readable reason

Rows carry the exact rule matches in `tag_rule_sources`; this makes every tag auditable.

## Current CoorsTek-Oriented Buckets

The first-pass taxonomy focuses on:

- `environmental_air`
- `environmental_water`
- `environmental_waste`
- `occupational_safety`
- `workplace_health`
- `labor_employment`
- `wage_hour`
- `energy_utilities`
- `mining_minerals_natural_resources`
- `chemicals_exposure`
- `transportation_hazmat`
- `building_fire_industrial_operations`
- `materials_product_compliance`
- `general_manufacturing`

These are metadata filters, not final legal conclusions. A row tagged `manufacturing`
means the agency/title/citation metadata suggests manufacturing relevance; it does not
prove the rule applies to a specific facility or process.

Broad filter aliases are accepted for convenience:

- `environmental` expands to `environmental_air`, `environmental_water`, and
  `environmental_waste`.
- `labor` expands to `labor_employment` and `wage_hour`.
- `ehs` expands to environmental, occupational-safety, workplace-health, and
  chemicals-exposure domains.
- `manufacturing` expands to `general_manufacturing`.
- `coorstek` expands to all high-value CoorsTek-oriented domains.

## Commands

Tag the full normalized CCR dataset and write summary counts:

```bash
python -m geode.connectors.ccr_industry_filter --output-root .
```

All manufacturing-related items:

```bash
python -m geode.connectors.ccr_industry_filter \
  --output-root . \
  --include-industry manufacturing \
  --include-domain general_manufacturing \
  --match-mode any \
  --filtered-prefix ccr_items_manufacturing
```

Environmental items:

```bash
python -m geode.connectors.ccr_industry_filter \
  --output-root . \
  --include-domain environmental \
  --filtered-prefix ccr_items_environmental
```

Labor/employment items:

```bash
python -m geode.connectors.ccr_industry_filter \
  --output-root . \
  --include-topic labor_employment \
  --include-domain labor \
  --match-mode any \
  --filtered-prefix ccr_items_labor_employment
```

High-confidence manufacturing environmental items:

```bash
python -m geode.connectors.ccr_industry_filter \
  --output-root . \
  --include-industry manufacturing \
  --include-domain environmental \
  --match-mode all \
  --min-confidence-score 0.85 \
  --filtered-prefix ccr_items_manufacturing_environmental_high
```

## Known Limitations

- CCR source metadata is often only citation, agency, department, and attachment URL.
- Rule titles may be unavailable until document text is converted and parsed.
- Broad agencies can produce broad tags; the rule match list and confidence label are
  meant to keep this visible.
- The filter does not replace schema-valid regulation extraction or site-specific legal
  analysis.
- Domain tags are filter-specific triage labels, while industry/topic tags use Geode
  controlled vocabularies where available.
