from __future__ import annotations

import re
from dataclasses import dataclass

from demiurg.claude_code import ClaudeCodeClient


@dataclass(slots=True)
class ValidationResult:
    accept: bool
    gaps: list[str]
    project_md: str


class Validator:
    """validate design/spec quality before planning"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.claude = ClaudeCodeClient(model="sonnet")

    async def validate(self, design_text: str) -> ValidationResult:
        prompt = f"""You are a strict design reviewer for Demiurg's planner-worker-judge flow.
Decide if the design is specific enough that the planner can generate concrete tasks
and the workers can produce a clear, verifiable outcome.

Design:
{design_text}

Return ONLY this XML:
<validation>
<decision>accept|reject</decision>
<gaps>
<gap>Missing explicit target language/framework</gap>
</gaps>
<project>
...PROJECT.md content if accepted...
</project>
</validation>

Rules:
- Reject if key details are missing (language, runtime, interface/IO, scope, constraints).
- Reject if the desired end state is not clearly testable or observable.
- Reject if the design would likely produce ambiguous tasks or unclear "done" criteria.
- If accepted, output empty <gaps></gaps>.
- If accepted, generate a concise PROJECT.md that clarifies the goal, stack,
  IO surfaces, constraints, and success criteria. Use markdown.
- If rejected, output empty <project></project>.
- Be concise and specific in each gap."""

        if self.verbose:
            print(f"\n{'='*60}")
            print("📤 VALIDATOR PROMPT:")
            print(f"{'='*60}")
            print(prompt)
            print(f"{'='*60}\n")

        result = await self.claude.execute(prompt, timeout=60)

        if self.verbose:
            print(f"\n{'='*60}")
            print("📥 VALIDATOR RESPONSE:")
            print(f"{'='*60}")
            print(result)
            print(f"{'='*60}\n")

        return self._parse(result)

    def _parse(self, text: str) -> ValidationResult:
        decision_match = re.search(r"<decision>(.*?)</decision>", text, re.DOTALL)
        decision = (decision_match.group(1).strip().lower() if decision_match else "")
        accept = decision == "accept"

        gaps = []
        for m in re.findall(r"<gap>(.*?)</gap>", text, re.DOTALL):
            gap = m.strip()
            if gap:
                gaps.append(gap)

        project_match = re.search(r"<project>(.*?)</project>", text, re.DOTALL)
        project_md = project_match.group(1).strip() if project_match else ""

        return ValidationResult(accept=accept, gaps=gaps, project_md=project_md)
