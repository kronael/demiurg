# specification

## goal

demonstrate planner-worker-judge pattern for scaling autonomous agents to large codebases, based on cursor's blog post.

goal-oriented execution: runs until satisfied, then exits (not a daemon).

## requirements

### execution model

- one-off execution (not continuous daemon)
- single planner at startup (generates all tasks upfront)
- workers execute tasks until complete
- judge polls for completion, exits when done
- no http api (removed for simplicity)
- no cycles (runs once until complete)

### agent coordination

- planner runs once at startup
- workers execute tasks independently without coordination
- judge polls state and exits when complete
- no locks between agents (only state manager uses asyncio.Lock)

### task management

- tasks have explicit states: pending, running, completed, failed
- tasks persist to disk (survive restart)
- queue unbounded, regenerated from pending tasks on continuation
- workers block on empty queue (no polling)

### state persistence

- all state stored as json files at ~/.demiurg/data
- tasks.json contains all task metadata
- work.json contains design_file, goal_text, is_complete flag
- state written on every change
- state loaded on startup

### concurrency

- single planner (runs once)
- configurable number of workers (default 4)
- single judge (polls every 5s)
- graceful shutdown on KeyboardInterrupt
- asyncio task cancellation propagates to workers

### configuration

- .env config files (not toml)
- precedence: env vars > ./.demiurg > ~/.demiurg/config
- defaults for all settings except CLAUDE_API_KEY
- validation on load (raises RuntimeError if key missing)

### logging

- unix timestamp format (2026/01/16 08:00:00)
- lowercase messages
- logs to ~/.demiurg/log/demiurg.log (not stdout)
- configurable log directory

## constraints

- single node only (no distributed coordination)
- in-memory queue (regenerated from state)
- python with asyncio (not Go)
- mock workers (no llm integration yet)
- no git operations
- no sub-planner spawning
- no conflict resolution
- no task retry logic
- no http api

## non-goals

- production deployment
- horizontal scaling
- high availability
- real code analysis (workers mocked)
- version control integration
- web ui
- metrics collection
- observability platform integration

this is a learning implementation, not production system.
