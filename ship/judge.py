from __future__ import annotations

import asyncio
import logging
import uuid

from ship.claude_code import ClaudeCodeClient
from ship.display import display, log_entry, write_progress_md
from ship.prompts import JUDGE_TASK
from ship.refiner import Refiner
from ship.replanner import Replanner
from ship.state import StateManager
from ship.types_ import Task, TaskStatus


MAX_RETRIES = 10


class Judge:
    """per-task judgment, batch refinement, full replanning

    narrow: judge each completed task individually (did it work?)
    medium: codex refines when batch completes (what's missing?)
    wide:   replanner assesses everything (what was the goal again?)
    """

    def __init__(
        self,
        state: StateManager,
        queue: asyncio.Queue[Task],
        project_context: str = "",
        max_refine_rounds: int = 10,
        max_replan_rounds: int = 1,
        verbosity: int = 1,
        session_id: str | None = None,
    ):
        self.state = state
        self.queue = queue
        self.project_context = project_context
        self.verbosity = verbosity
        self.max_refine_rounds = max_refine_rounds
        self.max_replan_rounds = max_replan_rounds
        self.refine_count = 0
        self.replan_count = 0
        self.worker_tasks: dict[str, str] = {}
        self.claude = ClaudeCodeClient(
            model="sonnet",
            role="judge",
            session_id=str(uuid.uuid4()),
        )
        self.refiner = Refiner(
            state,
            project_context,
            verbosity=verbosity,
        )
        self.replanner = Replanner(
            state,
            project_context,
            verbosity=verbosity,
            session_id=session_id,
        )
        self._completed_queue: list[Task] = []

    def set_worker_task(self, worker_id: str, desc: str) -> None:
        self.worker_tasks[worker_id] = desc

    def clear_worker_task(self, worker_id: str) -> None:
        self.worker_tasks.pop(worker_id, None)

    def notify_completed(self, task: Task) -> None:
        """worker calls this when a task finishes"""
        self._completed_queue.append(task)

    async def _judge_task(self, task: Task) -> None:
        """narrow: ask LLM to verify just this one task"""
        prompt = JUDGE_TASK.format(
            description=task.description,
            result=(task.result or "")[:500],
        )

        display.event(f"  judging: {task.description[:50]}", min_level=2)

        try:
            await self.claude.execute(prompt, timeout=45)
        except RuntimeError as e:
            logging.warning(f"judge task failed: {e}")
            log_entry(f"judge skip: {task.description[:40]}")

    def _build_task_panel(
        self,
        tasks: list[Task],
    ) -> list[tuple[str, TaskStatus, str]]:
        """build panel data from task list"""
        panel: list[tuple[str, TaskStatus, str]] = []
        for t in tasks:
            worker = ""
            if t.status is TaskStatus.RUNNING:
                for wid, desc in self.worker_tasks.items():
                    if desc == t.description:
                        worker = wid
                        break
            panel.append((t.description, t.status, worker))
        return panel

    def _update_tui(self, tasks: list[Task]) -> None:
        total = len(tasks)
        completed = len([t for t in tasks if t.status is TaskStatus.COMPLETED])
        running = len([t for t in tasks if t.status is TaskStatus.RUNNING])
        pending = len([t for t in tasks if t.status is TaskStatus.PENDING])
        failed = len([t for t in tasks if t.status is TaskStatus.FAILED])

        display.set_tasks(self._build_task_panel(tasks))
        display.set_phase(self._phase_label())
        display.refresh()

        workers = [f"{k}: {v}" for k, v in sorted(self.worker_tasks.items())]
        write_progress_md(
            total,
            completed,
            running,
            pending,
            failed,
            workers,
        )

    def _phase_label(self) -> str:
        if self.refine_count > 0:
            return f"refining ({self.refine_count}/{self.max_refine_rounds})"
        if self.replan_count > 0:
            return f"replanning ({self.replan_count}/{self.max_replan_rounds})"
        return "executing"

    async def run(self) -> None:
        """poll -> judge tasks -> retry -> refine -> replan"""
        logging.info("judge starting")
        display.event("  judge: monitoring...", min_level=2)

        try:
            while True:
                await asyncio.sleep(5)

                # judge newly completed tasks (narrow)
                while self._completed_queue:
                    task = self._completed_queue.pop(0)
                    await self._judge_task(task)

                all_tasks = await self.state.get_all_tasks()
                self._update_tui(all_tasks)

                # retry failed tasks
                retryable = [
                    t
                    for t in all_tasks
                    if t.status is TaskStatus.FAILED and t.retries < MAX_RETRIES
                ]
                for task in retryable:
                    await self.state.retry_task(task.id)
                    await self.queue.put(task)
                    log_entry(f"retry: {task.description[:50]}")
                    display.event(
                        f"  retry {task.id[:8]} ({task.retries + 1}/{MAX_RETRIES})"
                    )

                if not await self.state.is_complete():
                    continue

                # batch done - refine (medium)
                if self.refine_count < self.max_refine_rounds:
                    self.refine_count += 1
                    display.event(
                        f"  refining ({self.refine_count}/{self.max_refine_rounds})...",
                        min_level=2,
                    )
                    display.set_phase(self._phase_label())
                    display.refresh()
                    new_tasks = await self.refiner.refine()
                    if new_tasks:
                        log_entry(f"+{len(new_tasks)} from refiner")
                        display.event(f"  +{len(new_tasks)} follow-up tasks")
                        for task in new_tasks:
                            await self.queue.put(task)
                        continue

                # replan (wide)
                if self.replan_count < self.max_replan_rounds:
                    self.replan_count += 1
                    display.event(
                        f"  replanning ({self.replan_count}"
                        f"/{self.max_replan_rounds})...",
                        min_level=2,
                    )
                    display.set_phase(self._phase_label())
                    display.refresh()
                    new_tasks = await self.replanner.replan()
                    if new_tasks:
                        log_entry(f"+{len(new_tasks)} from replanner")
                        display.event(f"  +{len(new_tasks)} replanned tasks")
                        for task in new_tasks:
                            await self.queue.put(task)
                        continue

                # done
                display.event("  all tasks complete")
                logging.info("goal satisfied")
                await self.state.mark_complete()
                return

        except asyncio.CancelledError:
            logging.info("judge stopping")
            raise
