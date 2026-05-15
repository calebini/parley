# Parley Spec Tracking Matrix

Updated: 2026-05-15

Purpose: track the latest working version of each Parley spec across source docs and Whetstone run artifacts. The current working draft may be the source doc after apply-back or a Whetstone `spec.md` that has not yet been applied back to `docs/`.

## Accounting Notes

- `Lineage tokens` and `Whetstone time` are cumulative across the tracked run roots listed in [Run Lineage Counted](#run-lineage-counted), not just the current/latest run.
- `Whetstone time` uses Whetstone `telemetry_totals.total_duration_ms`, rounded to the nearest minute. It is telemetry wall time spent inside Whetstone runs, not human calendar time.
- Total tracked Whetstone usage across this matrix: 37 run roots, 38,515,608 tokens, 39h 33m.
- Legacy `*-mvp-003` runs are retained in lineage totals when they exist, even when the current working path has moved to the HLD-context rerun series.

## Status Legend

- `SOURCE_APPLIED`: Whetstone output has been applied back and the source doc matches the current run draft.
- `SOURCE_AHEAD_OF_RUN`: Whetstone output was applied back, then the source doc received an explicit post-apply update; source is now the working authority and no longer hash-matches the run draft.
- `CONVERGED_PENDING_APPLY_BACK`: Whetstone converged, but source doc does not yet match the run draft.
- `TARGET_NOT_REACHED`: Phase 1 exhausted the current target/budget and requires manual review, continuation, or bounded synthesis before continuing.
- `HALTED_CLIENT_TIMEOUT`: Phase 1 halted on a client timeout; resume only if Whetstone reports it as resumable.
- `HALTED_OSCILLATION`: Phase 1 halted on oscillation and requires manual review.
- `INCOMPLETE`: latest run artifacts are incomplete or failed validation and need continuation or repair before review.
- `MANUAL_SYNTHESIS_PENDING_WHETSTONE`: source doc has been manually synthesized ahead of the tracked Whetstone draft and should receive a focused Whetstone verification pass before being treated as settled.
- `NO_RUN_TRACKED`: no Whetstone run has been identified for this doc.

## Operator Recommendation Legend

- `BUILD_TARGET`: current source/draft is a reasonable implementation target.
- `LEAN_REWRITE_RECOMMENDED`: Whetstone converged or clarified the material, but implementation should prefer a lean rewrite from the accepted intent rather than treating the full text as the most ergonomic build contract.
- `RISK_DISCOVERY_ONLY`: useful as a risk map, but not recommended as the direct build target.
- `NEEDS_SYNTHESIS`: useful material exists, but the spec needs a bounded synthesis pass before implementation or apply-back.
- `DEPENDENCY_CONTEXT_ONLY`: use as navigation or dependency context, not as an implementation target.

## Decision Pressure Legend

- `low`: 0-10 human decisions.
- `medium`: 11-40 human decisions.
- `high`: 41-100 human decisions.
- `extreme`: 100+ human decisions.

## Apply-Back Safety Legend

- `SAFE_TO_APPLY`: converged with low enough decision pressure to apply after normal review.
- `REVIEW_DECISIONS_FIRST`: convergence exists, but human-decision pressure is high enough that operator review should precede or accompany apply-back.
- `DO_NOT_APPLY_DIRECTLY`: do not apply the current Whetstone draft directly; synthesize or restart from a clearer target.
- `SOURCE_ALREADY_AUTHORITY`: source doc is already the intended authority.

## Primary Matrix

| Spec | Source doc | Current working draft | Current Whetstone status | Operator recommendation | Apply-back safety | Source relation | Decision pressure | Runs counted | Lineage tokens | Whetstone time | Decision count | Human decisions | Next action / notes |
|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| HLD / Architecture | [docs/hld-architecture.md](hld-architecture.md) | [hld-architecture-mvp-001/spec.md](../whetstone_runs/hld-architecture-mvp-001/spec.md) | `CONVERGED` Phase 2 round 4 (`convergence_strict_check`) | `BUILD_TARGET` | `SOURCE_ALREADY_AUTHORITY` | `SOURCE_AHEAD_OF_RUN` | `medium` | 1 | 937,639 | 1h 08m | 19 | 14 | Source is authoritative and includes the post-apply MVP decision to defer paired-file mode / project-scope report roots. |
| Spec Index | [docs/specs/00-spec-index.md](specs/00-spec-index.md) | [00-spec-index-mvp-003/spec.md](../whetstone_runs/00-spec-index-mvp-003/spec.md) | `CONTEXT_ONLY` from accidental Phase 1 run | `DEPENDENCY_CONTEXT_ONLY` | `DO_NOT_APPLY_DIRECTLY` | Not applied | `medium` | 1 | 651,153 | 0h 32m | 28 | 21 | Navigation/dependency context only; do not interpret the run as a failed implementation-spec pass. |
| CLI Command | [docs/specs/01-cli-command-spec.md](specs/01-cli-command-spec.md) | [01-cli-command-spec-hld-mvp-012-phase1-final-sweep/spec.md](../whetstone_runs/01-cli-command-spec-hld-mvp-012-phase1-final-sweep/spec.md) | `CONVERGED` Phase 2 round 7 (`convergence_strict_check`) | `LEAN_REWRITE_RECOMMENDED` | `REVIEW_DECISIONS_FIRST` | `SOURCE_APPLIED` | `high` | 13 | 13,461,850 | 15h 56m | 66 | 65 | Applied back from the converged HLD-guided lineage, but decision pressure says treat it as a rich build source rather than a perfectly lean implementation contract. |
| Project Artifact Schema | [docs/specs/02-project-artifact-schema-spec.md](specs/02-project-artifact-schema-spec.md) | [docs/specs/02-project-artifact-schema-spec.md](specs/02-project-artifact-schema-spec.md) | `CONVERGED` Phase 2 round 14 (`scope_guard`, utility MVP closeout) | `BUILD_TARGET` | `REVIEW_DECISIONS_FIRST` | `SOURCE_APPLIED` | `medium` | 10 | 5,546,540 | 4h 41m | 12 | 12 | Applied back from the converged utility-MVP profile-set run. Build target is good, but review the 12 checkpointed decisions around report envelope, failure categories, schema versioning, TM boundary, and glossary severity before treating every detail as equally intentional. |
| Parser Interface and Format | [docs/specs/03-parser-interface-format-spec.md](specs/03-parser-interface-format-spec.md) | [03-parser-interface-format-spec-hld-mvp-001/spec.md](../whetstone_runs/03-parser-interface-format-spec-hld-mvp-001/spec.md) | `TARGET_NOT_REACHED` Phase 1 round 20 | `NEEDS_SYNTHESIS` | `DO_NOT_APPLY_DIRECTLY` | Not applied | `extreme` | 2 | 3,054,874 | 3h 16m | 159 | 159 | Latest HLD-context Phase 1 did not reach target; continue/recheck with HLD authority. |
| Placeholder and Token Integrity | [docs/specs/04-placeholder-token-integrity-spec.md](specs/04-placeholder-token-integrity-spec.md) | [04-placeholder-token-integrity-spec-hld-mvp-001/spec.md](../whetstone_runs/04-placeholder-token-integrity-spec-hld-mvp-001/spec.md) | `TARGET_NOT_REACHED` Phase 1 round 20 | `NEEDS_SYNTHESIS` | `DO_NOT_APPLY_DIRECTLY` | Not applied | `extreme` | 2 | 2,948,589 | 2h 51m | 147 | 147 | Latest HLD-context Phase 1 did not reach target; continue or synthesize likely hotspots. |
| Confidence Model | [docs/specs/05-confidence-model-spec.md](specs/05-confidence-model-spec.md) | [05-confidence-model-spec-hld-mvp-001/spec.md](../whetstone_runs/05-confidence-model-spec-hld-mvp-001/spec.md) | `CONVERGED` Phase 2 round 8 (`convergence_strict_check`) | `LEAN_REWRITE_RECOMMENDED` | `REVIEW_DECISIONS_FIRST` | `SOURCE_APPLIED` | `extreme` | 2 | 3,191,459 | 2h 39m | 139 | 139 | Applied back from converged HLD-context run, but extreme decision pressure suggests using it as a source of accepted intent and simplifying during implementation. |
| Translation Workflow | [docs/specs/06-translation-workflow-spec.md](specs/06-translation-workflow-spec.md) | [06-translation-workflow-spec-hld-mvp-001/spec.md](../whetstone_runs/06-translation-workflow-spec-hld-mvp-001/spec.md) | `HALTED_CLIENT_TIMEOUT` Phase 1 round 22 (`operability`) | `NEEDS_SYNTHESIS` | `DO_NOT_APPLY_DIRECTLY` | Not applied | `extreme` | 2 | 2,588,941 | 2h 31m | 215 | 215 | Latest HLD-context run halted on client timeout in operability; resume if Whetstone reports resumable. |
| Validation and Error Taxonomy | [docs/specs/07-validation-error-taxonomy-spec.md](specs/07-validation-error-taxonomy-spec.md) | [07-validation-error-taxonomy-spec-hld-mvp-001/spec.md](../whetstone_runs/07-validation-error-taxonomy-spec-hld-mvp-001/spec.md) | `CONVERGED` Phase 2 round 6 (`convergence_strict_check`) | `BUILD_TARGET` | `REVIEW_DECISIONS_FIRST` | `SOURCE_APPLIED` | `high` | 2 | 1,618,579 | 1h 08m | 67 | 67 | Applied back from converged HLD-context run. Buildable, but review the high-pressure decision surface before treating every detail as equally intentional. |
| Translation Memory | [docs/specs/08-translation-memory-spec.md](specs/08-translation-memory-spec.md) | [08-translation-memory-spec-hld-mvp-001/spec.md](../whetstone_runs/08-translation-memory-spec-hld-mvp-001/spec.md) | `TARGET_NOT_REACHED` Phase 1 round 21 | `NEEDS_SYNTHESIS` | `DO_NOT_APPLY_DIRECTLY` | Not applied | `extreme` | 2 | 4,515,984 | 4h 50m | 142 | 142 | Latest HLD-context Phase 1 did not reach target; continue or synthesize before Phase 2. |

## Run Lineage Counted

| Spec | Run roots included in lineage totals |
|---|---|
| HLD / Architecture | [`hld-architecture-mvp-001`](../whetstone_runs/hld-architecture-mvp-001) |
| Spec Index | [`00-spec-index-mvp-003`](../whetstone_runs/00-spec-index-mvp-003) |
| CLI Command | [`01-cli-command-spec-hld-mvp-001`](../whetstone_runs/01-cli-command-spec-hld-mvp-001)<br>[`01-cli-command-spec-hld-mvp-002-round29-closeout-check`](../whetstone_runs/01-cli-command-spec-hld-mvp-002-round29-closeout-check)<br>[`01-cli-command-spec-hld-mvp-003-determinism-continue`](../whetstone_runs/01-cli-command-spec-hld-mvp-003-determinism-continue)<br>[`01-cli-command-spec-hld-mvp-004-determinism-continue-timeout1800`](../whetstone_runs/01-cli-command-spec-hld-mvp-004-determinism-continue-timeout1800)<br>[`01-cli-command-spec-hld-mvp-005-determinism-synthesis`](../whetstone_runs/01-cli-command-spec-hld-mvp-005-determinism-synthesis)<br>[`01-cli-command-spec-hld-mvp-006-determinism-synthesis`](../whetstone_runs/01-cli-command-spec-hld-mvp-006-determinism-synthesis)<br>[`01-cli-command-spec-hld-mvp-007-validate-report-determinism`](../whetstone_runs/01-cli-command-spec-hld-mvp-007-validate-report-determinism)<br>[`01-cli-command-spec-hld-mvp-008-operability-check`](../whetstone_runs/01-cli-command-spec-hld-mvp-008-operability-check)<br>[`01-cli-command-spec-hld-mvp-009-operability-synthesis`](../whetstone_runs/01-cli-command-spec-hld-mvp-009-operability-synthesis)<br>[`01-cli-command-spec-hld-mvp-010-structural-integrity-check`](../whetstone_runs/01-cli-command-spec-hld-mvp-010-structural-integrity-check)<br>[`01-cli-command-spec-hld-mvp-011-structural-per-key-outcomes`](../whetstone_runs/01-cli-command-spec-hld-mvp-011-structural-per-key-outcomes)<br>[`01-cli-command-spec-hld-mvp-012-phase1-final-sweep`](../whetstone_runs/01-cli-command-spec-hld-mvp-012-phase1-final-sweep)<br>[`01-cli-command-spec-mvp-003`](../whetstone_runs/01-cli-command-spec-mvp-003) |
| Project Artifact Schema | [`02-project-artifact-schema-spec-hld-mvp-001`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-001)<br>[`02-project-artifact-schema-spec-hld-mvp-002-lean-synthesis-check`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-002-lean-synthesis-check)<br>[`02-project-artifact-schema-spec-hld-mvp-003-lean-synthesis-check`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-003-lean-synthesis-check)<br>[`02-project-artifact-schema-spec-hld-mvp-004-lean-synthesis-determinism-check`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-004-lean-synthesis-determinism-check)<br>[`02-project-artifact-schema-spec-hld-mvp-005-source-determinism-recheck`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-005-source-determinism-recheck)<br>[`02-project-artifact-schema-spec-hld-mvp-006-inventory-hash-determinism-recheck`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-006-inventory-hash-determinism-recheck)<br>[`02-project-artifact-schema-spec-hld-mvp-007-operability-recheck`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-007-operability-recheck)<br>[`02-project-artifact-schema-spec-hld-mvp-008-operability-final-recheck`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-008-operability-final-recheck)<br>[`02-project-artifact-schema-spec-hld-mvp-007-utility-mvp-phase1-sweep`](../whetstone_runs/02-project-artifact-schema-spec-hld-mvp-007-utility-mvp-phase1-sweep)<br>[`02-project-artifact-schema-spec-mvp-003`](../whetstone_runs/02-project-artifact-schema-spec-mvp-003) |
| Parser Interface and Format | [`03-parser-interface-format-spec-hld-mvp-001`](../whetstone_runs/03-parser-interface-format-spec-hld-mvp-001)<br>[`03-parser-interface-format-spec-mvp-003`](../whetstone_runs/03-parser-interface-format-spec-mvp-003) |
| Placeholder and Token Integrity | [`04-placeholder-token-integrity-spec-hld-mvp-001`](../whetstone_runs/04-placeholder-token-integrity-spec-hld-mvp-001)<br>[`04-placeholder-token-integrity-spec-mvp-003`](../whetstone_runs/04-placeholder-token-integrity-spec-mvp-003) |
| Confidence Model | [`05-confidence-model-spec-hld-mvp-001`](../whetstone_runs/05-confidence-model-spec-hld-mvp-001)<br>[`05-confidence-model-spec-mvp-003`](../whetstone_runs/05-confidence-model-spec-mvp-003) |
| Translation Workflow | [`06-translation-workflow-spec-hld-mvp-001`](../whetstone_runs/06-translation-workflow-spec-hld-mvp-001)<br>[`06-translation-workflow-spec-mvp-003`](../whetstone_runs/06-translation-workflow-spec-mvp-003) |
| Validation and Error Taxonomy | [`07-validation-error-taxonomy-spec-hld-mvp-001`](../whetstone_runs/07-validation-error-taxonomy-spec-hld-mvp-001)<br>[`07-validation-error-taxonomy-spec-mvp-003`](../whetstone_runs/07-validation-error-taxonomy-spec-mvp-003) |
| Translation Memory | [`08-translation-memory-spec-hld-mvp-001`](../whetstone_runs/08-translation-memory-spec-hld-mvp-001)<br>[`08-translation-memory-spec-mvp-003`](../whetstone_runs/08-translation-memory-spec-mvp-003) |

## Docs Without Tracked Whetstone Run

No tracked spec docs were found without a Whetstone run. Current docs scanned:

- [docs/hld-architecture.md](hld-architecture.md)
- [docs/specs/00-spec-index.md](specs/00-spec-index.md)
- [docs/specs/01-cli-command-spec.md](specs/01-cli-command-spec.md)
- [docs/specs/02-project-artifact-schema-spec.md](specs/02-project-artifact-schema-spec.md)
- [docs/specs/03-parser-interface-format-spec.md](specs/03-parser-interface-format-spec.md)
- [docs/specs/04-placeholder-token-integrity-spec.md](specs/04-placeholder-token-integrity-spec.md)
- [docs/specs/05-confidence-model-spec.md](specs/05-confidence-model-spec.md)
- [docs/specs/06-translation-workflow-spec.md](specs/06-translation-workflow-spec.md)
- [docs/specs/07-validation-error-taxonomy-spec.md](specs/07-validation-error-taxonomy-spec.md)
- [docs/specs/08-translation-memory-spec.md](specs/08-translation-memory-spec.md)

## Candidate Priority Queue

1. Use the HLD + Project Artifact Schema + CLI spec as the foundation for the first implementation slice, starting with project root detection and `parley project init` artifact creation.
2. Resume or synthesize the halted Translation Workflow HLD-context run if Whetstone reports it as resumable.
3. Continue or bounded-synthesize the remaining non-converged HLD-context runs: Translation Memory, Parser Interface and Format, and Placeholder and Token Integrity.
4. Treat the Spec Index as navigation/dependency context unless an explicit index cleanup pass is desired.

## Maintenance Notes

- Update this matrix after each Whetstone run, focused recheck, Phase 2 convergence, strop, or apply-back.
- When a spec has multiple Whetstone attempts, add the run root to [Run Lineage Counted](#run-lineage-counted) and refresh lineage totals.
- Prefer linking `Current working draft` to the source doc when a manual synthesis has intentionally moved source ahead of Whetstone; otherwise link to the run-level `spec.md` when it contains the latest accepted Whetstone draft.
- If source docs receive post-apply manual updates, mark `SOURCE_AHEAD_OF_RUN` rather than pretending the source still hash-matches the Whetstone run draft.
