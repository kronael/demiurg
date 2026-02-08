# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

autonomous agent orchestration implementing cursor's planner-worker-judge pattern.

## build and run

```bash
make build              # uv sync (install deps)
make install            # install as uv tool
make test               # pytest
make right              # pyright + pytest
make clean              # remove cache and state
```

run locally:
```bash
demiurg                 # reads DESIGN.md by default
demiurg -f spec.txt     # specify design file
demiurg -c              # continue from last run
demiurg -w 8 -t 1200    # 8 workers, 20min timeout
demiurg -v              # verbose mode (show prompts and responses)
```

## CLI (click-based)

entry point: `demiurg.__main__:run` using click decorators.

```python
@click.command()
@click.argument("design", required=False)
@click.option("-f", "--file", ...)
@click.option("-c", "--continue", "cont", is_flag=True, ...)
@click.option("-w", "--workers", type=int, ...)
@click.option("-t", "--timeout", type=int, ...)
@click.option("-m", "--max-turns", type=int, ...)
@click.option("-v", "--verbose", is_flag=True, ...)
def run(...):
```

defaults:
- design file: DESIGN.md (no positional arg required)
- max_turns: 25 (agentic turns per task)
- task_timeout: 1200s (20 minutes, agent told 10 minutes)
- workers: 4

## critical patterns

### enum checking
```python
if task.status is TaskStatus.PENDING:  # use 'is' not ==
```

### state mutations
- ALWAYS acquire lock before reading/writing state
- ALWAYS call save() while holding write lock
- ALWAYS copy data structures before returning (prevent mutation)

### config loading
- loads from ./.env if exists (via python-dotenv)
- environment variables override .env settings
- CLI args override env vars
- all settings optional with defaults
- no API key needed (uses claude code CLI session)

### continuation flow
```python
if cont:
    await state.reset_interrupted_tasks()  # running -> pending
    pending = await state.get_pending_tasks()
    for task in pending:
        await queue.put(task)
```

## shocking patterns

**judge exits (not continuous)**: judge task completes when goal satisfied.
no daemon mode, no http server - just runs until done.

**no queue persistence**: queue regenerated from pending tasks on continuation.

**single planner at startup**: planner runs once to break design into tasks,
then exits. no continuous planning.

**async locks everywhere**: state manager uses asyncio.Lock for all mutations.

**streaming output**: workers stream claude CLI output line-by-line during
execution. prints in real-time prefixed with worker ID.

**permission mode hardcoded**: claude CLI always called with
`--permission-mode acceptEdits` to auto-approve file edits.

**codex for critique**: refiner uses Codex CLI (non-streaming) to generate
follow-up tasks after worker completion.

**replanning phase**: if refinement yields no new work, judge triggers a
single replanning round via Claude to catch missing tasks or alternative
approaches.

**task sizing guidance**: planner told tasks should be completable in 2 days
(underestimates scope) to generate smaller, focused tasks. workers told 10min
timeout (actual 20min) to work efficiently.

**dynamic worker scaling**: adjusts worker count to task count at startup
(min(cfg.num_workers, len(pending_tasks))). never spawns more than tasks.

## architecture

### execution flow
1. parse args (design file path or -c for continuation)
2. load config from env/.env files
3. init state manager (loads from ./.demiurg/)
4. if new run:
   - validator checks DESIGN.md quality (rejects to REJECTION.md if underspecified)
   - validator writes PROJECT.md on accept
   - planner.plan_once() parses design file into tasks
   - state.init_work() creates work.json
5. if continuation (-c):
   - load existing work.json
   - reset interrupted tasks (running -> pending)
6. populate queue from pending tasks
7. spawn workers (default 4) and judge
8. workers pull tasks from queue and execute
9. judge polls every 5s, exits when all tasks complete
10. main() cancels workers and exits

### task states
explicit enum in types_.py: PENDING, RUNNING, COMPLETED, FAILED

### state persistence
all state at ./.demiurg/ (project-local):
- tasks.json: array of all tasks with metadata
- work.json: design_file, goal_text, is_complete
- log/: execution logs

### key files
- `__main__.py`: entry point, orchestrates planner/workers/judge
- `config.py`: load config from environment variables
- `state.py`: StateManager with async locks
- `types_.py`: Task, TaskStatus, WorkState dataclasses
- `planner.py`: parse design file into tasks using Claude CLI
- `validator.py`: reject underspecified designs to REJECTION.md; generate PROJECT.md
- `worker.py`: execute tasks from queue using ClaudeCodeClient
- `claude_code.py`: isolated client for calling claude code CLI
- `judge.py`: poll for completion every 5s, exit when done
- `refiner.py`: create follow-up tasks using Codex CLI
- `replanner.py`: propose new tasks using Claude CLI if refinement is empty

## configuration

loads from ./.env (project-local) + environment variables:

- NUM_WORKERS=4
- TASK_TIMEOUT=1200 (seconds, default 20min; agent told 10min)
- MAX_TURNS=25 (agentic turns per task)
- LOG_DIR=.demiurg/log
- DATA_DIR=.demiurg

no API key required - uses authenticated claude code CLI session.

## commit messages

format: `[section] message`
- lowercase, imperative mood
- example: `[config] remove unused PORT and NUM_PLANNERS`
