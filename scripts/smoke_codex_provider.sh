#!/usr/bin/env bash
set -euo pipefail

if [[ "${PARLEY_RUN_CODEX_SMOKE:-}" != "1" ]]; then
  echo "Refusing to run real Codex CLI smoke without PARLEY_RUN_CODEX_SMOKE=1." >&2
  echo "This smoke uses only synthetic strings, but it may use local Codex credentials/network." >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project_root="$(mktemp -d "${TMPDIR:-/tmp}/parley-codex-smoke.XXXXXX")"

mkdir -p "${project_root}/en.lproj" "${project_root}/fr.lproj"
printf '"hello" = "Hello, %%@";\n' > "${project_root}/en.lproj/Localizable.strings"
: > "${project_root}/fr.lproj/Localizable.strings"

export PYTHONPATH="${repo_root}/src"

python3 -m parley project init \
  --project-root "${project_root}" \
  --name CodexSmoke \
  --authoritative "${project_root}/en.lproj/Localizable.strings" \
  --locale en-US \
  --format ios_strings

python3 -m parley context seed \
  --project-root "${project_root}" \
  --mode placeholder

set +e
python3 -m parley localization add \
  "${project_root}/fr.lproj/Localizable.strings" \
  --project-root "${project_root}" \
  --locale fr-FR \
  --format ios_strings
add_status=$?
set -e

if [[ "${add_status}" != "0" && "${add_status}" != "1" ]]; then
  echo "localization add failed unexpectedly with exit ${add_status}" >&2
  exit "${add_status}"
fi

translate_output="$(
  python3 -m parley translate \
    --project-root "${project_root}" \
    --target-locale fr-FR \
    --reuse-mode provider_only \
    --provider command-json \
    --provider-command "${repo_root}/scripts/codex_parley_provider.py" \
    --provider-response-mode stdout_json \
    --provider-timeout-seconds 180
)"

echo "${translate_output}"
report_path="$(printf '%s\n' "${translate_output}" | awk -F= '/^report=/{print $2}')"

python3 - "${project_root}" "${report_path}" <<'PY'
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1])
report_path = Path(sys.argv[2])
target_path = project_root / "fr.lproj" / "Localizable.strings"

target_text = target_path.read_text(encoding="utf-8")
if "%@" not in target_text:
    raise SystemExit("target file did not preserve %@ placeholder")
if '"hello"' not in target_text:
    raise SystemExit("target file does not contain hello key")
if "Hello, %@" in target_text:
    raise SystemExit("target file still contains untranslated source text")

payload = json.loads(report_path.read_text(encoding="utf-8"))
summary = payload.get("summary", {})
if payload.get("exit_code") != 0:
    raise SystemExit(f"translate report exit_code was {payload.get('exit_code')}")
if payload.get("provider_status") != "used":
    raise SystemExit(f"provider_status was {payload.get('provider_status')}")
if summary.get("generated_count") != 1:
    raise SystemExit(f"generated_count was {summary.get('generated_count')}")
if summary.get("tm_written") is not True:
    raise SystemExit("translation memory was not written")
if summary.get("written_target") is not True:
    raise SystemExit("target file was not written")

print(f"codex smoke project: {project_root}")
print(f"codex smoke target: {target_path}")
print(f"codex smoke report: {report_path}")
PY
