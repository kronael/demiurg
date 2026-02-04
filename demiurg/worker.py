from __future__ import annotations

import asyncio
import logging

from demiurg.claude_code import ClaudeCodeClient
from demiurg.config import Config
from demiurg.skills import format_skills_for_prompt, load_skills
from demiurg.state import StateManager
from demiurg.types_ import Task, TaskStatus


class Worker:
    """executes tasks from queue using claude code CLI"""
    def __init__(self, worker_id: str, cfg: Config, state: StateManager, project_context: str = ""):
        self.worker_id = worker_id
        self.cfg = cfg
        self.state = state
        self.project_context = project_context
        self.skills = load_skills()
        self.claude = ClaudeCodeClient(
            model="sonnet",
            max_turns=cfg.max_turns,
        )

    async def run(self, queue: asyncio.Queue[Task]) -> None:
        """process tasks from queue until cancelled"""
        logging.info(f"{self.worker_id} starting")

        try:
            while True:
                task = await queue.get()
                try:
                    await self._execute(task)
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            logging.info(f"{self.worker_id} stopping")
            raise

    async def _execute(self, task: Task) -> None:
        print(f"\n🤖 [{self.worker_id}] {task.description}")

        await self.state.update_task(task.id, TaskStatus.RUNNING)

        try:
            result = await self._do_work(task)

            # check if max turns error appeared in output
            if "reached max turns" in result.lower():
                await self.state.update_task(
                    task.id, TaskStatus.FAILED, error="reached max turns"
                )
                print(f"⚠️  [{self.worker_id}] max turns reached - task incomplete")
                logging.warning(f"{self.worker_id} max turns: {task.description}")
                return

            await self.state.update_task(
                task.id, TaskStatus.COMPLETED, result=result
            )
            print(f"✅ [{self.worker_id}] done!")
            logging.info(f"{self.worker_id} completed: {task.description}")

        except RuntimeError as e:
            # claude CLI errors (including timeout) come as RuntimeError
            error_msg = str(e) if str(e) else type(e).__name__
            await self.state.update_task(
                task.id, TaskStatus.FAILED, error=error_msg
            )
            if "timeout" in error_msg.lower():
                print(f"⏱️  [{self.worker_id}] timeout after {self.cfg.task_timeout}s")
                logging.warning(f"{self.worker_id} {error_msg}: {task.description}")
            else:
                print(f"❌ [{self.worker_id}] error: {error_msg}")
                logging.error(f"{self.worker_id} failed: {task.description}: {error_msg}")

        except Exception as e:
            error_msg = str(e) if str(e) else type(e).__name__
            await self.state.update_task(
                task.id, TaskStatus.FAILED, error=error_msg
            )
            print(f"❌ [{self.worker_id}] error: {error_msg}")
            logging.error(
                f"{self.worker_id} failed: {task.description}: {error_msg}"
            )

    async def _do_work(self, task: Task) -> str:
        """execute task by calling claude code CLI with streaming output"""
        # build prompt with context, skills, and task
        parts = []

        if self.project_context:
            parts.append(f"Project: {self.project_context}")

        if self.skills:
            skills_text = format_skills_for_prompt(self.skills)
            if skills_text:
                parts.append(skills_text)
                parts.append("Use the relevant skills above for this task.")

        parts.append("IMPORTANT: You have a 10-minute timeout for this task. Work efficiently and focus on completing the task within this timeframe.")
        parts.append(f"Task: {task.description}")

        prompt = "\n\n".join(parts)

        if self.cfg.verbose:
            print(f"\n{'='*60}")
            print(f"📤 PROMPT TO CLAUDE:")
            print(f"{'='*60}")
            print(prompt)
            print(f"{'='*60}\n")
            print(f"📥 RESPONSE FROM CLAUDE:")
            print(f"{'='*60}\n")

        output_lines = []
        async for line in self.claude.execute_stream(prompt, timeout=self.cfg.task_timeout):
            if line.strip():
                if self.cfg.verbose:
                    # in verbose mode, just print raw output
                    print(f"   {line}")
                else:
                    # add visual indicators for different types of output
                    if line.startswith("Error:"):
                        print(f"   ⚠️  {line}")
                    elif any(word in line.lower() for word in ["writing", "creating", "adding"]):
                        print(f"   ✏️  {line}")
                    elif any(word in line.lower() for word in ["reading", "analyzing", "checking"]):
                        print(f"   👀 {line}")
                    elif any(word in line.lower() for word in ["running", "executing", "testing"]):
                        print(f"   ⚡ {line}")
                    else:
                        print(f"   💭 {line}")
            output_lines.append(line)

        if self.cfg.verbose:
            print(f"\n{'='*60}")
            print(f"✅ END OF RESPONSE")
            print(f"{'='*60}\n")

        return "\n".join(output_lines)
