from __future__ import annotations

import logging
import re
import uuid

from demiurg.claude_code import ClaudeCodeClient
from demiurg.config import Config
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Planner:
    """breaks down design files into executable tasks using claude code CLI"""

    def __init__(self, cfg: Config, state: StateManager):
        self.cfg = cfg
        self.state = state
        self.claude = ClaudeCodeClient(model="sonnet")

    async def plan_once(self) -> list[Task]:
        """break down goal into tasks (runs once)"""
        work = self.state.get_work_state()
        if not work:
            return []

        logging.info("breaking down goal into tasks")

        # extract project context and tasks together
        context, tasks = await self._parse_design(work.goal_text)

        # store context for workers
        if context:
            await self.state.set_project_context(context)
            logging.info(f"project context: {context[:100]}...")

        for task in tasks:
            await self.state.add_task(task)
            logging.info(f"created task: {task.description}")

        return tasks

    async def _parse_design(self, goal: str) -> tuple[str, list[Task]]:
        """parse design doc into context and tasks using Claude"""
        prompt = f"""Analyze this design document and extract:
1. A brief project context (what's being built, language/framework, purpose)
2. Executable tasks

<design>
{goal}
</design>

Output format - return ONLY this XML:

<project>
<context>Brief 1-2 sentence description of what's being built and key technologies</context>
<tasks>
<task>Create go.mod with module name and dependencies</task>
<task>Implement HTTP server with health endpoint</task>
</tasks>
</project>

Rules for tasks:
- Each task is a concrete, completable coding action
- Task description starts with a verb (Create, Add, Implement, Write)
- Skip explanations, examples, documentation
- Consolidate related items when sensible"""

        try:
            result = await self.claude.execute(prompt, timeout=60)
            return self._parse_xml(result)
        except RuntimeError as e:
            logging.warning(f"claude parsing failed: {e}")
            return "", []

    def _parse_xml(self, text: str) -> tuple[str, list[Task]]:
        """extract context and tasks from XML response"""
        # extract context
        context_match = re.search(r"<context>(.*?)</context>", text, re.DOTALL)
        context = context_match.group(1).strip() if context_match else ""

        # extract tasks
        tasks = []
        task_pattern = r"<task>(.*?)</task>"
        matches = re.findall(task_pattern, text, re.DOTALL)

        for desc in matches:
            desc = desc.strip()
            if desc and len(desc) > 5:
                task = Task(
                    id=str(uuid.uuid4()),
                    description=desc,
                    files=[],
                    status=TaskStatus.PENDING,
                )
                tasks.append(task)

        return context, tasks
