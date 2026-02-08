from __future__ import annotations

import asyncio
import logging

from demiurg.replanner import Replanner
from demiurg.refiner import Refiner
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Judge:
    """polls for task completion, runs refinement, exits when truly done"""

    def __init__(
        self,
        state: StateManager,
        queue: asyncio.Queue[Task],
        project_context: str = "",
        max_refine_rounds: int = 3,
        max_replan_rounds: int = 1,
        verbose: bool = False,
    ):
        self.state = state
        self.queue = queue
        self.refiner = Refiner(state, project_context, verbose=verbose)
        self.replanner = Replanner(state, project_context, verbose=verbose)
        self.max_refine_rounds = max_refine_rounds
        self.max_replan_rounds = max_replan_rounds
        self.refine_count = 0
        self.replan_count = 0

    async def run(self) -> None:
        """check completion every 5s, run refinement when batch done"""
        logging.info("judge starting")
        print("\n👨‍⚖️  judge: monitoring progress...\n")
        idle_ticks = 0

        try:
            while True:
                await asyncio.sleep(5)
                idle_ticks += 1

                if idle_ticks % 2 == 0:
                    # heartbeat with task status summary
                    all_tasks = await self.state.get_all_tasks()
                    pending = len([t for t in all_tasks if t.status is TaskStatus.PENDING])
                    running = len([t for t in all_tasks if t.status is TaskStatus.RUNNING])
                    completed = len([t for t in all_tasks if t.status is TaskStatus.COMPLETED])
                    failed = len([t for t in all_tasks if t.status is TaskStatus.FAILED])
                    total = len(all_tasks)
                    print(f"⏳ judge: status {completed}/{total} completed, {running} running, {pending} pending, {failed} failed")

                if await self.state.is_complete():
                    idle_ticks = 0
                    # all current tasks done - try refinement
                    if self.refine_count < self.max_refine_rounds:
                        print(f"\n🔍 judge: checking for follow-up work (round {self.refine_count + 1}/{self.max_refine_rounds})...")
                        logging.info(f"running refinement round {self.refine_count + 1}")
                        new_tasks = await self.refiner.refine()

                        if new_tasks:
                            self.refine_count += 1
                            print(f"📋 judge: found {len(new_tasks)} follow-up tasks\n")
                            logging.info(f"refiner created {len(new_tasks)} follow-up tasks")
                            for task in new_tasks:
                                await self.queue.put(task)
                            continue  # keep running, workers will pick up new tasks
                        self.refine_count += 1

                    # if refinement yields nothing, attempt a replan once
                    if self.replan_count < self.max_replan_rounds:
                        print(f"\n🧭 judge: attempting replanning (round {self.replan_count + 1}/{self.max_replan_rounds})...")
                        logging.info(f"running replanning round {self.replan_count + 1}")
                        new_tasks = await self.replanner.replan()

                        if new_tasks:
                            self.replan_count += 1
                            print(f"📋 judge: replanner added {len(new_tasks)} tasks\n")
                            logging.info(f"replanner created {len(new_tasks)} tasks")
                            for task in new_tasks:
                                await self.queue.put(task)
                            continue
                        self.replan_count += 1

                    # no new tasks or max rounds reached
                    print("\n🎯 judge: all tasks complete!\n")
                    logging.info("goal satisfied, marking complete")
                    await self.state.mark_complete()
                    return

        except asyncio.CancelledError:
            logging.info("judge stopping")
            raise
