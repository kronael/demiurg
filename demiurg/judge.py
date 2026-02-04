from __future__ import annotations

import asyncio
import logging

from demiurg.refiner import Refiner
from demiurg.state import StateManager
from demiurg.types_ import Task


class Judge:
    """polls for task completion, runs refinement, exits when truly done"""

    def __init__(
        self,
        state: StateManager,
        queue: asyncio.Queue[Task],
        project_context: str = "",
        max_refine_rounds: int = 3,
        verbose: bool = False,
    ):
        self.state = state
        self.queue = queue
        self.refiner = Refiner(state, project_context, verbose=verbose)
        self.max_refine_rounds = max_refine_rounds
        self.refine_count = 0

    async def run(self) -> None:
        """check completion every 5s, run refinement when batch done"""
        logging.info("judge starting")
        print("\n👨‍⚖️  judge: monitoring progress...\n")

        try:
            while True:
                await asyncio.sleep(5)

                if await self.state.is_complete():
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

                    # no new tasks or max rounds reached
                    print("\n🎯 judge: all tasks complete!\n")
                    logging.info("goal satisfied, marking complete")
                    await self.state.mark_complete()
                    return

        except asyncio.CancelledError:
            logging.info("judge stopping")
            raise
