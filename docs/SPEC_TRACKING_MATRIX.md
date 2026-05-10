# Parley Spec Tracking Matrix

Updated: 2026-05-10

Purpose: track the latest working version of each Parley spec across source docs and Whetstone run artifacts. The "current working draft" may be a Whetstone `spec.md` that has not been applied back to `docs/` yet.

## Status Legend

- `SOURCE_APPLIED`: Whetstone output has been applied back to the source doc.
- `CONVERGED_PENDING_APPLY_BACK`: Whetstone converged, but source doc does not yet match the run draft.
- `PHASE_1_TARGET_NOT_REACHED`: Phase 1 exhausted the current target/budget and requires manual review before continuing.
- `PHASE_1_HALTED_CLIENT_TIMEOUT`: Phase 1 halted on a client timeout; the run may be resumable.
- `PHASE_1_HALTED_OSCILLATION`: Phase 1 halted on oscillation and requires manual review.
- `PHASE_1_INCOMPLETE`: Phase 1 has an incomplete/latest round or failed run artifact state and needs continuation or repair.
- `NO_RUN_TRACKED`: no Whetstone run has been identified for this doc.

## Primary Matrix

| Spec | Source doc | Current working draft | Current Whetstone status | Apply-back | Tokens | Decision count | Human decisions | Next action / notes |
|---|---|---|---|---|---:|---:|---:|---|
| HLD / Architecture | [docs/hld-architecture.md](hld-architecture.md) | [hld-architecture-mvp-001/spec.md](../whetstone_runs/hld-architecture-mvp-001/spec.md) | `CONVERGED_PENDING_APPLY_BACK` Phase 2 round 14 | Review available, not applied | 1,875,278 | 19 | 14 | Convergence declaration accepted with zero unresolved blockers, major issues, or rubric gaps. Source doc still matches the pre-run hash. |
| Spec Index | [docs/specs/00-spec-index.md](specs/00-spec-index.md) | [00-spec-index-mvp-003/spec.md](../whetstone_runs/00-spec-index-mvp-003/spec.md) | `PHASE_1_TARGET_NOT_REACHED` round 16 | Not available | 651,153 | 28 | 21 | Manual review required. Source differs from current run draft. |
| CLI Command | [docs/specs/01-cli-command-spec.md](specs/01-cli-command-spec.md) | [01-cli-command-spec-mvp-003/spec.md](../whetstone_runs/01-cli-command-spec-mvp-003/spec.md) | `PHASE_1_TARGET_NOT_REACHED` round 21 | Not available | 1,504,877 | 159 | 159 | Manual review required. Source differs from current run draft. |
| Project Artifact Schema | [docs/specs/02-project-artifact-schema-spec.md](specs/02-project-artifact-schema-spec.md) | [02-project-artifact-schema-spec-mvp-003/spec.md](../whetstone_runs/02-project-artifact-schema-spec-mvp-003/spec.md) | `PHASE_1_TARGET_NOT_REACHED` round 27 | Not available | 2,112,773 | 143 | 131 | Manual review required. Source differs from current run draft. |
| Parser Interface and Format | [docs/specs/03-parser-interface-format-spec.md](specs/03-parser-interface-format-spec.md) | [03-parser-interface-format-spec-mvp-003/spec.md](../whetstone_runs/03-parser-interface-format-spec-mvp-003/spec.md) | `PHASE_1_HALTED_CLIENT_TIMEOUT` round 19 | Not available | 1,216,746 | 175 | 169 | Resumable client timeout in `operability`; resume or increase timeout. Source differs from current run draft. |
| Placeholder and Token Integrity | [docs/specs/04-placeholder-token-integrity-spec.md](specs/04-placeholder-token-integrity-spec.md) | [04-placeholder-token-integrity-spec-mvp-003/spec.md](../whetstone_runs/04-placeholder-token-integrity-spec-mvp-003/spec.md) | `PHASE_1_TARGET_NOT_REACHED` round 20 | Not available | 1,354,013 | 123 | 123 | Manual review required. Source differs from current run draft. |
| Confidence Model | [docs/specs/05-confidence-model-spec.md](specs/05-confidence-model-spec.md) | [05-confidence-model-spec-mvp-003/spec.md](../whetstone_runs/05-confidence-model-spec-mvp-003/spec.md) | `PHASE_1_TARGET_NOT_REACHED` round 18 | Not available | 1,006,412 | 125 | 108 | Manual review required. Source differs from current run draft. |
| Translation Workflow | [docs/specs/06-translation-workflow-spec.md](specs/06-translation-workflow-spec.md) | [06-translation-workflow-spec-mvp-003/spec.md](../whetstone_runs/06-translation-workflow-spec-mvp-003/spec.md) | `PHASE_1_INCOMPLETE` round 13 | Not available | 807,555 | n/a | n/a | Phase 1 exited with incomplete round artifacts and no decision summary; continue or repair before review. Source differs from current run draft. |
| Validation and Error Taxonomy | [docs/specs/07-validation-error-taxonomy-spec.md](specs/07-validation-error-taxonomy-spec.md) | [07-validation-error-taxonomy-spec-mvp-003/spec.md](../whetstone_runs/07-validation-error-taxonomy-spec-mvp-003/spec.md) | `PHASE_1_HALTED_OSCILLATION` round 11 | Not available | 412,377 | 26 | 24 | Manual review required after determinism oscillation/blocker. Source differs from current run draft. |
| Translation Memory | [docs/specs/08-translation-memory-spec.md](specs/08-translation-memory-spec.md) | [08-translation-memory-spec-mvp-003/spec.md](../whetstone_runs/08-translation-memory-spec-mvp-003/spec.md) | `PHASE_1_HALTED_CLIENT_TIMEOUT` round 28 | Not available | 2,387,175 | 201 | 201 | Resumable client timeout in `operability`; resume or increase timeout. Source differs from current run draft. |

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

1. Resume or rerun timeout-halting specs: Parser Interface and Format, Translation Memory.
2. Repair or continue the incomplete Translation Workflow run before interpreting its review state.
3. Manual review before further Phase 1 work: Spec Index, CLI Command, Project Artifact Schema, Placeholder and Token Integrity, Confidence Model, Validation and Error Taxonomy.
4. HLD / Architecture: review the accepted convergence draft and decide whether to apply it back to `docs/hld-architecture.md`.

## Maintenance Notes

- Update this matrix after each Whetstone run, focused recheck, Phase 2 convergence, or apply-back.
- Prefer linking the current working draft to the run-level `spec.md` when it contains the latest accepted draft.
- If a run halts with an incomplete latest round, keep `spec.md` as the current working draft and note the incomplete round in the status/notes.
- If apply-back is run, update the source doc status and keep the Whetstone run root as the provenance record.
