# architecture

## overview

demiurg implements planner-worker-judge pattern from cursor's blog post on scaling autonomous coding agents (https://cursor.com/blog/scaling-agents). goal-oriented execution: runs until satisfied, then exits.

```
design.txt → Planner → [task, task, task] → Queue
                                              ↓
                              Worker ← Worker ← Worker ← Worker
                                              ↓
                                          State (JSON)
                                              ↓
                                           Judge → exit when complete
```

## components

### planner

reads design file, breaks into tasks using LLM (currently mocked).

runs once at startup. generates tasks with:
- unique id (uuid)
- description (e.g., "create function foo()")
- empty files list (populated by worker)
- status (pending)

adds tasks to state and submits to queue.

### queue

asyncio.Queue holding pending tasks. unbounded (no maxsize).

workers block on queue.get() until task available.

no persistence - regenerated from state on continuation.

### worker

fetches tasks from queue, executes them, updates state.

execution flow:
1. mark task as running
2. call LLM with task description + codebase context (currently mocked - sleeps 1s)
3. write/modify files based on response
4. mark task as completed with result

on error: mark task as failed with error message.

30s timeout per task.

workers run independently - no inter-worker communication.

### judge

polls state every 5s.

checks completion: no pending/running tasks AND at least one task exists.

when complete:
- marks work.is_complete = true
- logs "goal satisfied"
- exits (cancels worker tasks)

### state manager

persists to ~/.demiurg/data as json files:
- tasks.json: array of all tasks with metadata
- work.json: design_file, goal_text, is_complete flag

async locks (asyncio.Lock) protect concurrent access.

loads existing state on startup for continuation.

## data flow

1. main() parses args (design file or -c flag)
2. if new run:
   - planner.plan_once() generates tasks
   - state.init_work() creates work state
3. if continuation:
   - state.reset_interrupted_tasks() resets running → pending
4. populate queue from pending tasks
5. workers pull from queue, execute, update state
6. judge polls every 5s:
   - if complete: mark work.is_complete, exit
   - else: continue polling
7. on judge exit: cancel workers, shutdown

## task lifecycle

states (explicit enum in types.py):
- pending: created, not yet started
- running: worker executing
- completed: finished successfully
- failed: error during execution

transitions:
- pending → running (worker.execute start)
- running → completed (worker.execute success)
- running → failed (worker.execute error)
- running → pending (continuation after interruption)

no retry logic - failed tasks stay failed.

## concurrency model

all agents run as asyncio tasks spawned from main.

coordination:
- queue uses asyncio.Queue (no locks needed)
- state manager uses asyncio.Lock
- workers don't coordinate with each other
- judge only reads state

shutdown:
- judge exits when complete
- main() cancels worker tasks
- gather with return_exceptions=True waits for cancellation

no coordination between workers - eliminates cursor's lock bottleneck.

## continuation model

state tracks interrupted work:
- work.json stores design_file and goal_text
- running tasks reset to pending on startup
- queue regenerated from pending tasks
- workers continue from last checkpoint

continuation flow:
```bash
# start work
demiurg design.txt  # creates work.json, generates tasks

# interrupt (ctrl-c)
^C

# continue
demiurg -c  # loads work.json, resets running tasks, resumes
```

## persistence format

tasks.json:
```json
[
  {
    "id": "uuid",
    "description": "create function foo()",
    "files": [],
    "status": "completed",
    "created_at": "2026-01-16T08:00:00Z",
    "started_at": "2026-01-16T08:00:05Z",
    "completed_at": "2026-01-16T08:00:06Z",
    "result": "created foo() in main.py"
  }
]
```

work.json:
```json
{
  "design_file": "design.txt",
  "goal_text": "- Create function foo()\n- Add tests",
  "is_complete": false
}
```

## configuration precedence

1. defaults (hardcoded in config.py)
2. ~/.demiurg/config (global .env file)
3. ./.demiurg (local project .env file)
4. environment variables (highest priority)

uses python-dotenv to load .env files.

defaults:
- claude_api_key: (required, no default)
- num_workers: 4
- num_planners: 2
- target_dir: "."
- log_dir: ~/.demiurg/log
- data_dir: ~/.demiurg/data
- port: 8080

## logging

unix format: "2026/01/16 08:00:00"

logs to: ~/.demiurg/log/demiurg.log

lowercase messages, capitalize error names only.

## simplifications

compared to cursor's blog post, this implementation omits:
- continuous daemon mode (one-off execution instead)
- http api (removed for simplicity)
- multiple planners (single planner at startup)
- cycles (runs once until complete)
- git operations (checkout, commit, push)
- real llm integration (workers currently mocked)
- queue persistence (regenerated from state)
- conflict resolution
- dynamic task prioritization
- multi-node coordination

these simplifications make the system suitable for learning the pattern, not production use.
