# demiurg: autonomous coding agent

## what it is

goal-oriented code generation agent that reads a design file, breaks it into tasks, executes them in parallel, and exits when done. no daemon, no http server, no manual intervention.

## why it matters

**traditional approaches fail at scale:**
- manual coding: slow, error-prone, doesn't scale
- chatbots: require constant supervision, lose context, can't parallelize
- code assistants: need hand-holding through each step

**demiurg runs autonomously:**
- reads design.txt describing what you want
- breaks goal into concrete tasks using claude
- executes 4 tasks in parallel (configurable)
- each task gets full claude code access (read/write files, bash, web)
- judge monitors completion, exits when goal satisfied
- state persisted to ./.demiurg/ (resume anytime with -c)

## value proposition

**save 10-100x time on boilerplate:**
- API server? write design.txt with endpoints, run demiurg, done
- migration script? describe the transformation, run demiurg, done
- test suite? specify test cases, run demiurg, done

**true parallelization:**
- 4 workers executing simultaneously (not sequential chat)
- tasks run independently, state isolated
- no coordination overhead, no context switching

**project isolation:**
- each project has ./.demiurg/ state (tasks.json, work.json, log/)
- run multiple demiurg instances on different projects simultaneously
- no global state mixing, no conflicts

**continuation built-in:**
- ctrl-c? run `demiurg -c` to resume
- crashed? tasks automatically reset from running → pending
- no lost work, no manual recovery

## how it works

```bash
# create design file
cat > design.txt <<EOF
- create fastapi server with /health endpoint
- add GET /users endpoint with pagination
- add POST /users endpoint with validation
- write pytest tests for all endpoints
- add openapi documentation
EOF

# run demiurg (once)
demiurg design.txt

# it will:
# 1. parse design.txt into 5 tasks using claude
# 2. spawn 4 workers, execute tasks in parallel
# 3. each worker calls: claude -p "<task>" --model sonnet
# 4. judge polls every 5s, exits when all tasks complete
# 5. you have a working API server
```

## comparison

| approach | time | parallelization | supervision | state |
|----------|------|-----------------|-------------|-------|
| manual coding | days | none (one brain) | constant | mental |
| chatgpt | hours | none (sequential) | constant | lost after session |
| cursor | hours | none (one task at a time) | per-task | project files |
| **demiurg** | **minutes** | **4 workers** | **zero** | **./.demiurg/** |

## architecture

based on cursor's scaling agents blog:
- **planner**: reads design file, creates tasks (runs once at startup)
- **workers**: execute tasks in parallel using claude code CLI
- **judge**: polls every 5s, exits when goal satisfied

pattern proven at scale by cursor, implemented for command-line use.

## requirements

- claude code CLI installed (`claude --version`)
- python 3.13+
- that's it

## installation

```bash
# run directly from github
uvx github.com/kronael/demiurg design.txt

# or install globally
make install
demiurg design.txt
```

## when to use

**perfect for:**
- boilerplate generation (APIs, CLIs, scripts)
- migrations and transformations
- test suite creation
- documentation generation
- repetitive coding tasks

**not for:**
- creative problem solving (use claude code directly)
- debugging complex issues (use IDE)
- learning new concepts (use chatgpt)
- small one-off changes (edit manually)

## shocking truths

- runs until done, then exits (not a long-running service)
- planner runs once at startup (no continuous planning)
- workers timeout after 30s per task (forces atomic tasks)
- queue regenerated from pending tasks on continuation (no queue persistence)
- state isolated per project (no global ~/.demiurg mixing)

## bottom line

demiurg turns "I need to build X" into a design.txt file and walks away while 4 claude instances build it in parallel. no supervision, no context loss, no manual recovery.

**time saved = (hours of manual coding) - (minutes writing design.txt)**

typically 10-100x ROI on boilerplate. higher for larger projects.
