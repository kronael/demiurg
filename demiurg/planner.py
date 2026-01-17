from __future__ import annotations

import logging
import uuid

from demiurg.config import Config
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Planner:
    def __init__(self, cfg: Config, state: StateManager):
        self.cfg = cfg
        self.state = state

    async def plan_once(self) -> list[Task]:
        """break down goal into tasks (runs once)"""
        work = self.state.get_work_state()
        if not work:
            return []

        logging.info("breaking down goal into tasks")

        tasks = self._parse_tasks(work.goal_text)

        for task in tasks:
            await self.state.add_task(task)
            logging.info(f"created task: {task.description}")

        return tasks

    def _parse_tasks(self, goal: str) -> list[Task]:
        """parse goal text into tasks"""
        tasks = []
        lines = goal.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("-") or line.startswith("*"):
                desc = line.lstrip("-*").strip()
                if desc:
                    task = Task(
                        id=str(uuid.uuid4()),
                        description=desc,
                        files=[],
                        status=TaskStatus.PENDING,
                    )
                    tasks.append(task)

        if not tasks:
            task = Task(
                id=str(uuid.uuid4()),
                description=goal[:200],
                files=[],
                status=TaskStatus.PENDING,
            )
            tasks.append(task)

        return tasks
