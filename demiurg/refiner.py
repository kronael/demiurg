from __future__ import annotations

import logging
import re
import uuid

from demiurg.claude_code import ClaudeCodeClient
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Refiner:
    """analyzes completed work and creates follow-up tasks"""

    def __init__(self, state: StateManager, project_context: str = "", verbose: bool = False):
        self.state = state
        self.project_context = project_context
        self.verbose = verbose
        self.claude = ClaudeCodeClient(model="sonnet")

    async def refine(self) -> list[Task]:
        """analyze recent work and create follow-up tasks if needed"""
        all_tasks = await self.state.get_all_tasks()

        completed = [t for t in all_tasks if t.status is TaskStatus.COMPLETED]
        failed = [t for t in all_tasks if t.status is TaskStatus.FAILED]

        if not completed and not failed:
            return []

        # build summary of recent work
        completed_summary = "\n".join(f"- [DONE] {t.description}" for t in completed[-10:])
        failed_summary = "\n".join(f"- [FAILED] {t.description}: {t.error}" for t in failed[-5:])

        prompt = f"""Analyze this project's progress and determine if follow-up tasks are needed.

Project: {self.project_context}

Recent completed tasks:
{completed_summary or "None"}

Failed tasks:
{failed_summary or "None"}

Based on this progress:
1. Are there any obvious follow-up tasks needed (tests, fixes, integration)?
2. Do any failed tasks need alternative approaches?
3. Is there cleanup or documentation needed?

If follow-up tasks are needed, output them. If the work looks complete, output empty tasks.

<tasks>
<task>Add unit tests for the new HTTP handlers</task>
</tasks>

Or if complete:
<tasks>
</tasks>"""

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"📤 REFINER PROMPT:")
            print(f"{'='*60}")
            print(prompt)
            print(f"{'='*60}\n")

        try:
            result = await self.claude.execute(prompt, timeout=60)

            if self.verbose:
                print(f"\n{'='*60}")
                print(f"📥 REFINER RESPONSE:")
                print(f"{'='*60}")
                print(result)
                print(f"{'='*60}\n")

            new_tasks = self._parse_tasks(result)

            for task in new_tasks:
                await self.state.add_task(task)
                logging.info(f"refiner created task: {task.description}")

            return new_tasks
        except RuntimeError as e:
            logging.warning(f"refiner failed: {e}")
            return []

    def _parse_tasks(self, text: str) -> list[Task]:
        """extract tasks from XML response"""
        tasks = []
        pattern = r"<task>(.*?)</task>"
        matches = re.findall(pattern, text, re.DOTALL)

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

        return tasks
