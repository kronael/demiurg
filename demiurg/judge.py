from __future__ import annotations

import asyncio
import logging

from demiurg.state import StateManager


class Judge:
    """polls for task completion and exits when all tasks are done"""
    def __init__(self, state: StateManager):
        self.state = state

    async def run(self) -> None:
        """check if goal satisfied every 5s"""
        logging.info("judge starting")

        try:
            while True:
                await asyncio.sleep(5)

                if await self.state.is_complete():
                    logging.info("goal satisfied, marking complete")
                    await self.state.mark_complete()
                    return

        except asyncio.CancelledError:
            logging.info("judge stopping")
            raise
