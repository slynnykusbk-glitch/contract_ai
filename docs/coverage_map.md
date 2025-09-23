# Coverage map

The coverage map describes how document segments map to high level obligation zones.
It is stored in [`contract_review_app/legal_rules/coverage_map.yaml`](../contract_review_app/legal_rules/coverage_map.yaml)
and validated through [`coverage_map.py`](../contract_review_app/legal_rules/coverage_map.py).

## Schema overview

```yaml
version: 1
zones:
  - zone_id: payment
    zone_name: "Payment & Invoicing"
    description: "Optional human readable text"
    label_selectors:
      any: ["payment_terms", "payment_security", "late_payment_interest", ...]
      all: []                # optional set of labels that must all match
      none: []               # optional labels that prevent a match
    entity_selectors:
      amounts: true          # enable entity counters for a zone
      durations: false
      law: false
      jurisdiction: false
    rule_ids_opt: ["pay_late_interest_v1", ...]  # optional related rules
    weight: 1.0             # reserved for future weighting logic
    required: true          # zones we expect to always evaluate
```

All label selectors are normalised with the same tokeniser used for L0 features.
Aliases such as `governed_by` for `governing_law` are expanded automatically.

## Zone catalogue

The current catalogue contains 45 zones curated in
[`coverage_zones.py`](../contract_review_app/legal_rules/coverage_zones.py).
Each entry below lists the zone id, its intent and representative L0 labels used as selectors.

- **payment — Payment & Invoicing**: payment_terms, payment_security, late_payment_interest, service_credits, set_off, taxes_vat, open_book_pricing, rate_card
- **term — Term & Renewal**: term, renewal_auto, suspension, usage_limits, survival
- **termination — Termination Rights**: termination_breach, termination_convenience, termination_insolvency, termination_assistance, termination_change_of_control
- **notices — Notices**: notices, foi, lead_times, escalation, service_levels_sla
- **governing_law — Governing Law**: governing_law, severance, waiver, entire_agreement, third_party_rights, remedies
- **jurisdiction — Jurisdiction & Forum**: jurisdiction, dispute_resolution, arbitration, mediation, escalation
- **dispute_resolution — Dispute Resolution**: dispute_resolution, arbitration, mediation, escalation, foi
- **liability_cap — Liability & Caps**: limitation_of_liability, liability_cap_amount, liability_carveouts, indirect_consequential_exclusion, liquidated_damages, deductibles_limits
- **indemnity — Indemnities**: indemnity_general, ip_indemnity, dp_indemnity, waiver_of_subrogation, insurance_requirements
- **confidentiality — Confidentiality & Publicity**: confidentiality, nhs_patient_confidentiality, permitted_disclosures, return_or_destruction, announcements_publicity, transparency_publication
- **ip — Intellectual Property**: ip_ownership, license_grant, ip_indemnity, open_source, tooling, title_retention_rot
- **data_protection — Data Protection**: dp_general, dp_roles, dp_breach_notification, dp_security_measures, dp_subprocessing, dp_retention_deletion, dp_records_of_processing, dp_localisation, dp_dpia, dp_dsr
- **insurance — Insurance Requirements**: insurance_requirements, insurance_types_limits, waiver_of_subrogation, deductibles_limits, business_continuity_bcp
- **force_majeure — Force Majeure**: force_majeure, business_continuity_bcp, disaster_recovery, backup_restore, suspension, step_in_rights
- **taxes — Taxes & Withholding**: taxes_vat, anti_tax_evasion, price_changes_indexation, set_off, payment_terms
- **assignment — Assignment**: assignment, joa_assignment_consent, tenancy_assignment_underlet, third_party_rights, title_retention_rot
- **subcontracting — Subcontracting & Flow-down**: subcontracting, subprocessor_approval, dp_subprocessing, support_maintenance, staff_vetting
- **order_of_precedence — Order of Precedence**: entire_agreement, remedies, third_party_rights, waiver, severance
- **definitions — Definitions**: definitions, parties, interpretation, entire_agreement, remedies
- **interpretation — Interpretation**: interpretation, entire_agreement, severance, waiver, remedies
- **acceptance — Acceptance & Testing**: acceptance_testing, acceptance_it, quality_control_qc, warranty_conformity, service_levels_sla
- **delivery — Delivery & Performance**: delivery, delivery_terms_incoterms, risk_and_title, packaging_labelling, lead_times
- **service_levels — Service Levels & Credits**: service_levels_sla, service_credits, saas_uptime, support_maintenance, quality_control_qc
- **price_adjustment — Price Adjustments**: price_changes_indexation, open_book_pricing, rate_card, most_favoured_customer, usage_limits
- **interest_late — Late Payment Interest**: late_payment_interest, payment_terms, service_credits, taxes_vat, set_off
- **change_control — Change Control**: change_control, change_management_it, variation, construction_variations, construction_programme
- **audit_records — Audit & Records**: audit_rights, records_retention, dp_audit, dp_records_of_processing, dp_back_to_back
- **survival — Survival & Exit**: survival, termination_assistance, records_retention, return_or_destruction, dp_retention_deletion
- **personnel — Personnel & Conduct**: staff_vetting, onboarding_migration, equality_diversity, conflicts_of_interest, modern_slavery, nhs_safeguarding
- **cross_refs — Cross References**: entire_agreement, transparency_publication, foi, third_party_rights, remedies
- **warranties — Warranties**: warranty_conformity, warranty_performance, warranty_ip_noninfringe, warranty_doas_rma, quality_control_qc, remedies
- **quality — Quality & Standards**: quality_control_qc, construction_defects_liability, construction_programme, construction_retention, construction_eot, construction_variations, spares_obsolescence
- **health_safety — Health & Safety**: health_and_safety, hazardous_substances, nhs_serious_incident, nhs_safeguarding, construction_health_safety_cdm
- **compliance_abac — Compliance & ABAC**: anti_bribery, anti_tax_evasion, modern_slavery, equality_diversity, sanctions_export_controls, conflicts_of_interest
- **change_of_control — Change of Control**: termination_change_of_control, joa_operator, joa_opcom, joa_marketing, joa_default_nonconsent, joa_work_program_budget
- **background_ip — Background IP**: license_grant, title_retention_rot, tooling, joa_work_program_budget, joa_authorisation_for_expenditure
- **foreground_ip — Foreground IP**: ip_ownership, ip_indemnity, joa_joint_accounting, joa_marketing, joa_operator
- **records_retention — Records & Retention**: records_retention, dp_retention_deletion, dp_records_of_processing, return_or_destruction, dp_localisation
- **limitation_periods — Limitation Periods**: limitation_of_liability, liability_cap_amount, liability_carveouts, liquidated_damages, remedies
- **setoff_withholding — Set-off & Withholding**: set_off, taxes_vat, payment_terms, payment_security, anti_tax_evasion
- **export_controls_sanctions — Export Controls & Sanctions**: sanctions_export_controls, anti_bribery, anti_tax_evasion, modern_slavery, foi
- **escrow_source_code — Source Code Escrow**: escrow, backup_restore, disaster_recovery, business_continuity_bcp, tooling
- **step_in_rights — Step-in Rights**: step_in_rights, nhs_step_in, business_continuity_bcp, support_maintenance, disaster_recovery
- **novation — Novation & Transfer**: assignment, joa_assignment_consent, tenancy_assignment_underlet, third_party_rights, termination_change_of_control
- **non_solicit_non_compete — Non-solicit & Non-compete**: non_solicitation, staff_vetting, equality_diversity, conflicts_of_interest, nhs_safeguarding

## Auto-generation workflow

`tools/coverage_seed_from_repo.py` rebuilds the YAML file from repository metadata. The script:

1. Reads the canonical taxonomy (`LABELS_CANON`) and the declarative zone seeds in
   [`coverage_zones.py`](../contract_review_app/legal_rules/coverage_zones.py).
2. Matches label hints to existing L0 labels (with optional allow/deny lists) and
   enumerates rules whose identifiers, clause types or packs align with the rule hints.
3. Writes `coverage_map.yaml` and reports statistics:
   - number of zones,
   - percentage of labels used vs. the taxonomy,
   - percentage of rules covered, and
   - the top unused labels so curators can tighten gaps.

Run the tool directly:

```bash
python tools/coverage_seed_from_repo.py            # write YAML and emit report
python tools/coverage_seed_from_repo.py --dry-run  # show the generated YAML
```

The script is deterministic thanks to the curated hints and allow/deny lists. Manual
adjustments should happen in `coverage_zones.py`, not in the YAML file.

## Lint & thresholds

`tools/coverage_map_lint.py` validates both schema and curation quality. In strict
mode (`--strict` or `FEATURE_COVERAGE_LINT_STRICT=1`) the following thresholds are
checked:

- at least 30 zones in the map;
- ≥80% of YAML rules appear in `rule_ids_opt` for some zone;
- ≥70% of taxonomy labels (excluding service entries) are referenced by `label_selectors.any`;
- each high-importance zone (`payment`, `liability_cap`, `confidentiality`, `data_protection`,
  `governing_law`, `jurisdiction`, `dispute_resolution`, `force_majeure`, `notices`, `taxes`, `ip`)
  has five or more label selectors; and
- entity selectors in YAML match the curated matrix from `coverage_zones.py`.

The lint report prints summary metrics and highlights the top unused labels to aid
future tuning.

## Loader and coverage computation

`coverage_map.load_coverage_map()` reads the YAML file, validates the schema via
Pydantic and returns a cached structure containing:

- the original zone definitions,
- an index of label → zone ids, and
- an index of rule id → zone ids.

The loader is cached with `functools.lru_cache`. Use
`coverage_map.invalidate_cache()` to reload the file in development.

`coverage_map.build_coverage()` aggregates L0 labels, entities and rule firing
signals into a compact TRACE block. Inputs:

- `segments`: sequence of segments with labels, entities and spans,
- `dispatch_candidates_by_segment`: list of rule id sets per segment,
- `triggered_rule_ids`: fired YAML rules, and
- `rule_lookup`: optional map of rule metadata (for validation).

The output is compatible with `TRACE.add(..., "coverage", ...)`. Details are
clamped to 50 zones and three segments per zone to keep TRACE small. Raw text
snippets are removed during sanitisation.

Integration tests verify that the TRACE payload surfaces meaningful coverage on a
mix of real contract fixtures and that the aggregation stays performant.
