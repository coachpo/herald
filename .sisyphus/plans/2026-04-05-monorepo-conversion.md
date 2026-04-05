# Monorepo Conversion Plan

- Date: 2026-04-05
- Planner: Prometheus-style draft via Sisyphus-Junior
- Status: Approved by Momus

## Requirement Summary

Convert this repository from a superrepo with git submodules into a true monorepo, with no backward compatibility layer. `backend/`, `frontend/`, and `edge/` must remain at the same paths but become ordinary tracked directories inside the root repository.

## Execution Context

- Base ref: `origin/main` at `f60056a`
- Execution branch: `chore/monorepo-conversion-20260405`
- Worktree path: `/Users/liqing/Documents/PersonalProjects/My_Proj/herald-chore-monorepo-conversion-20260405`
- Former submodules:
  - `backend` @ `c7b68e529be4fc682438f8c1618c4b262ee99f95` (`heads/main`)
  - `frontend` @ `68718cffe162c7f4b73d3961322a42c9e0b9c2c4` (`heads/main`)
  - `edge` @ `87caa9d912779aebdeb096ad6d8830eac24abfc4` (`heads/main`)

## Scope

Included:
- Remove submodule metadata and gitlink entries.
- Materialize `backend/`, `frontend/`, and `edge/` as normal directory trees at the pinned SHAs above.
- Update root docs, root guidance, CI workflows, and root helper scripts to describe a monorepo directly.
- Verify repo state and existing package-level commands after the conversion.

Excluded:
- No backward compatibility for submodule checkout/init/update flows.
- No new root workspace toolchain beyond what is needed to reflect the new repo shape.
- No release, commit, rebase, push, or cleanup beyond implementation and verification.

## Ordered Implementation Steps
1. Record the base ref, execution branch, worktree path, and pinned package SHAs in this plan and later in the stop report.
2. Remove `.gitmodules` and replace the three gitlinks with normal tracked file trees rooted at `backend/`, `frontend/`, and `edge/`.
3. Remove execution-local nested Git admin metadata so the root repo no longer treats those directories as embedded repositories.
4. Update root surfaces that encode the superrepo model:
   - `README.md`
   - `AGENTS.md`
   - `docs/09_repo_structure.md`
   - `docs/07_operations.md`
   - `docs/02_architecture.md`
   - `docs/10_edge.md`
   - `docs/11_edge_lite_feasibility.md`
   - `.github/workflows/docker-images.yml`
   - `.github/workflows/cleanup.yml`
   - `start.sh`
   - `docker-compose.yml`
5. Verify the repo is no longer a submodule-based checkout.
6. Run package-level verification commands and a lightweight root smoke check.

## Task QA Scenarios

### Task 1: Baseline inventory
- Tool: `GIT_MASTER=1 git worktree list`, `GIT_MASTER=1 git submodule status --recursive`
- Steps: capture the execution worktree path, base ref, branch name, and the three pinned package SHAs before edits begin.
- Expected result: the stop report inputs match the initial inventory exactly.

### Task 2: Flatten Git structure
- Tool: `test ! -f .gitmodules`, `GIT_MASTER=1 git ls-files --stage`, `GIT_MASTER=1 git submodule status`
- Steps: remove `.gitmodules`, replace gitlinks with ordinary files, then check the index and submodule state.
- Expected result: `.gitmodules` is absent, `git submodule status` reports no active submodules, and `git ls-files --stage` has no `160000` entries for `backend`, `frontend`, or `edge`.

### Task 3: Remove nested Git metadata
- Tool: filesystem inspection plus `GIT_MASTER=1 git status --short`
- Steps: remove nested Git admin artifacts for `backend`, `frontend`, and `edge`, then confirm the root repo sees ordinary directory contents instead of embedded repos.
- Expected result: the root worktree reports normal tracked file changes under those directories with no embedded-repo warnings or submodule semantics.

### Task 4: Update root docs and automation
- Tool: targeted file reads plus `GIT_MASTER=1 git diff --stat`
- Steps: review each touched root doc/workflow/script after editing and confirm the superrepo/submodule language is gone.
- Expected result: the edited root surfaces describe a direct monorepo only, and the diff is limited to the expected documentation/workflow/script surfaces.

### Task 5: Repo-state verification
- Tool: `GIT_MASTER=1 git status --short`, `GIT_MASTER=1 git diff --stat`, `GIT_MASTER=1 git submodule status`, `GIT_MASTER=1 git ls-files --stage`
- Steps: run the repo-state checks after all structural and doc changes are complete.
- Expected result: the repo remains coherent, contains no gitlinks, and shows only expected conversion changes.

### Task 6: Package and root verification
- Tool: package commands and root smoke command
- Steps: run backend tests, frontend install/lint/build, edge install/test/lint, and `./start.sh --help`.
- Expected result: all listed commands exit successfully and provide the final verification wave for the approved scope.

## Atomic Execution Units

1. Git flattening unit
   - Remove `.gitmodules`, replace gitlinks with ordinary trees, and remove nested Git admin metadata.
   - If commits are requested later, this is one atomic commit boundary.
2. Root documentation and guidance unit
   - Update `README.md`, `AGENTS.md`, `docs/09_repo_structure.md`, `docs/07_operations.md`, `docs/02_architecture.md`, `docs/10_edge.md`, and `docs/11_edge_lite_feasibility.md`.
   - If commits are requested later, this is one atomic commit boundary.
3. Root automation unit
   - Update `.github/workflows/docker-images.yml`, `.github/workflows/cleanup.yml`, `start.sh`, and `docker-compose.yml`.
   - If commits are requested later, this is one atomic commit boundary.
4. Verification and stop-report unit
   - Run repo/package verification, update the stop report inputs, and stop before commit/rebase/cleanup.
   - This unit stays uncommitted in this workflow unless the user later requests commits.

## TDD-Oriented Execution Sequence

### Unit 1: Git flattening
- Pre-change assertions: `.gitmodules` exists, `GIT_MASTER=1 git submodule status` reports the three current submodules, and `GIT_MASTER=1 git ls-files --stage` contains `160000` entries for `backend`, `frontend`, and `edge`.
- Change: flatten the git structure into ordinary directories and remove nested Git metadata.
- Post-change assertions: `.gitmodules` is absent, `git submodule status` is empty, and no `160000` entries remain.

### Unit 2: Root documentation and guidance
- Pre-change assertions: targeted files still describe the repo as a superrepo/submodule-based checkout.
- Change: rewrite those files to describe a direct monorepo only.
- Post-change assertions: targeted reads confirm the submodule instructions and superrepo wording are gone.

### Unit 3: Root automation
- Pre-change assertions: workflow/script files still contain submodule-era assumptions such as recursive checkout or wording tied to submodule semantics.
- Change: rewrite the root automation surfaces to operate on in-tree directories only.
- Post-change assertions: targeted reads confirm the new monorepo wording/behavior, and `./start.sh --help` still works.

### Unit 4: Final verification wave
- Gate before finishing: backend tests, frontend install/lint/build, edge install/test/lint, and repo-state checks must pass before stopping.
- Expected result: the repo satisfies the acceptance criteria and is left ready for user review without commit/rebase/cleanup.

## Verification Commands

Repo state:
- `GIT_MASTER=1 git status --short`
- `GIT_MASTER=1 git diff --stat`
- `test ! -f .gitmodules`
- `GIT_MASTER=1 git submodule status`
- `GIT_MASTER=1 git ls-files --stage | rg '^160000 .*\t(backend|frontend|edge)$'`

Backend:
- `uv sync --project backend --locked`
- `uv run --project backend --locked pytest backend/tests/ -v`

Frontend (in `frontend/`):
- `pnpm install`
- `pnpm lint`
- `pnpm build`

Edge (in `edge/`):
- `npm install`
- `npm test`
- `npm run lint`

Root smoke:
- `./start.sh --help`

## Acceptance Criteria

- `.gitmodules` is removed.
- `GIT_MASTER=1 git submodule status` shows no active submodules.
- `GIT_MASTER=1 git ls-files --stage` contains no `160000` entries for `backend`, `frontend`, or `edge`.
- `backend/`, `frontend/`, and `edge/` are ordinary tracked directories at the same paths.
- Root docs, guidance, and workflows no longer describe or require submodule checkout/init/update flows.
- Existing package-level verification commands complete successfully.

## Risks And Mitigations

- Embedded Git metadata may survive the conversion and block a true monorepo state.
  - Mitigation: explicitly remove nested `.git` admin files/directories and confirm no gitlinks remain.
- Mixed docs or CI semantics may leave the repo internally inconsistent.
  - Mitigation: update every root surface that currently encodes the superrepo model in the same change.
- Scope creep into new workspace tooling could expand the migration unnecessarily.
  - Mitigation: keep backend/frontend/edge toolchains unchanged for this conversion.

## Rollback Notes

- Cleanest rollback point: restore the worktree to `origin/main` at `f60056a`.
- Do not leave the repo in a mixed state with both gitlinks and ordinary files.
- If rollback happens after partial flattening, restore `.gitmodules`, restore gitlinks to the pinned SHAs, and remove staged ordinary files under `backend/`, `frontend/`, and `edge/`.

## Stop Report Template

- Approved plan path: `.sisyphus/plans/2026-04-05-monorepo-conversion.md`
- Base ref used: `origin/main @ f60056a`
- Execution branch: `chore/monorepo-conversion-20260405`
- Worktree path: `/Users/liqing/Documents/PersonalProjects/My_Proj/herald-chore-monorepo-conversion-20260405`
- Former submodule SHAs:
  - `backend` @ `c7b68e529be4fc682438f8c1618c4b262ee99f95`
  - `frontend` @ `68718cffe162c7f4b73d3961322a42c9e0b9c2c4`
  - `edge` @ `87caa9d912779aebdeb096ad6d8830eac24abfc4`
- Tracked surfaces changed
- Repo-state verification results
- Package verification results
- Notes on nested Git metadata cleanup
- Explicit statement that commit, rebase, and cleanup were not performed by this workflow
