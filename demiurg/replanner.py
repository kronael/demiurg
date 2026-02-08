from __future__ import annotations

import logging
import re
import uuid

from demiurg.claude_code import ClaudeCodeClient
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Replanner:
    """revisits the plan based on progress and failures"""

    def __init__(self, state: StateManager, project_context: str = "", verbose: bool = False):
        self.state = state
        self.project_context = project_context
        self.verbose = verbose
        self.claude = ClaudeCodeClient(model="sonnet")

    async def replan(self) -> list[Task]:
        """create new tasks based on progress and failures"""
        work = self.state.get_work_state()
        if not work:
            return []

        all_tasks = await self.state.get_all_tasks()
        completed = [t for t in all_tasks if t.status is TaskStatus.COMPLETED]
        failed = [t for t in all_tasks if t.status is TaskStatus.FAILED]

        completed_summary = "\n".join(f"- [DONE] {t.description}" for t in completed[-10:])
        failed_summary = "\n".join(f"- [FAILED] {t.description}: {t.error}" for t in failed[-5:])

        prompt = f"""Replan the remaining work based on the project goal and progress.

Project: {self.project_context}

Goal:
{work.goal_text}

Completed tasks:
{completed_summary or "None"}

Failed tasks:
{failed_summary or "None"}

Output new executable tasks only if needed. If no further work is needed, return empty tasks.

<tasks>
<task>Implement X to replace failed approach Y</task>
</tasks>

Or if complete:
<tasks>
</tasks>"""

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"📤 REPLANNER PROMPT:")
            print(f"{'='*60}")
            print(prompt)
            print(f"{'='*60}\n")
        else:
            print("🧭 replanner: asking Claude to replan remaining work...")

        try:
            result = await self.claude.execute(prompt, timeout=60)

            if self.verbose:
                print(f"\n{'='*60}")
                print(f"📥 REPLANNER RESPONSE:")
                print(f"{'='*60}")
                print(result)
                print(f"{'='*60}\n")

            new_tasks = self._parse_tasks(result)
            for task in new_tasks:
                await self.state.add_task(task)
                logging.info(f"replanner created task: {task.description}")

            if not new_tasks:
                print("🧭 replanner: no new tasks suggested")
            return new_tasks
        except RuntimeError as e:
            logging.warning(f"replanner failed: {e}")
            print(f"⚠️  replanner: failed: {e}")
            return []

    def _parse_tasks(self, text: str) -> list[Task]:
        tasks = []
        pattern = r"<task>(.*?)</task>"
        matches = re.findall(pattern, text, re.DOTALL)

        for desc in matches:
            desc = desc.strip()
            if desc and len(desc) > 5:
                tasks.append(
                    Task(
                        id=str(uuid.uuid4()),
                        description=desc,
                        files=[],
                        status=TaskStatus.PENDING,
                    )
                )
        return tasks
