# Integration report

## Integrated delivery

- Task: `T-001`
- Worker commit: `a50305fc948d2779883bb90d6ea81e5b145084f0`
- Integration commit: `a2264c7`
- Scope verification: passed; no files outside the manifest write scope and
  the permitted handoff path.

The integration replaces the global compound table with
`PLATFORM_COMPOUND_OVERRIDES`. The classifier selects the table by
`post.platform` and passes it into the existing ordered longest-match masking
helper. No scoring, schema, import, collector, workflow, credential, or
deployment code changed.

## Executable gates

- Focused classifier/scoring suite: 39 passed.
- Full suite: 191 passed.
- `python -m compileall -q mom_index scripts tests pipeline.py`: passed.
- `python -m pip check`: no broken requirements.
- `node --check frontend/assets/app.js`: passed.
- Workflow YAML parse: passed.
- `scripts/build_site.py` and `scripts/check_site.py`: passed against a clean
  temporary output directory; six expected files were generated.
- `git diff --check`: passed in the worker before commit.

An initial local JavaScript gate used the wrong path `frontend/app.js` and
failed with `MODULE_NOT_FOUND`; repository CI/README evidence was inspected,
the command was corrected to `frontend/assets/app.js`, and the actual gate
passed. This was a verification-command error, not a product failure.

## Responsive visual QA

The generated schema-v3 site was served locally and inspected in the Codex
in-app browser.

- Desktop `1440x900`: all four concern headings present, all major panels
  bounded from x=134 to x=1306, page scroll width 1440 equals client width
  1440, and no console errors.
- Mobile `390x844`: all four concern headings present, all major panels bounded
  from x=12 to x=378, page scroll width 390 equals client width 390, and no
  console errors.
- Both widths visibly rendered the public-degradation state: Guba unavailable,
  Xiaohongshu unavailable, no successful live reading, and market context
  unavailable while the social formula remains independent.

Temporary viewport overrides were reset, the local QA tab was finalized, and
the temporary HTTP server was stopped. Generated site files and screenshots
were not committed.

## Consensus adjudication

- The previous Fable 5 concern about global compound overrides is fixed and
  covered by explicit XHS, Guba, and unknown-platform tests.
- Public market-unavailable behavior remains an intentional truthful release
  state because no compliant provider was authorized.
- The prior WorkBuddy permission incident remains process evidence only; it did
  not require a product change.
- Formula 1.1 is unchanged.

## Release boundary

No push, pull request, merge, public deployment, workflow change, or credential
use was performed. Release still requires explicit user approval.
