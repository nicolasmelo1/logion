"""DSPy Signature for the bootstrap decision policy.

The signature defines the input/output contract that DSPy optimizers will
compile against. The decision policy takes a user prompt, installed
capability index, marketplace search results, and the current bootstrap
policy text — and produces a structured action decision.
"""

from __future__ import annotations

from typing import Literal

import dspy

ActionKind = Literal[
    "answer_directly",
    "search_marketplace",
    "inspect_course",
    "ask_before_install",
    "ask_before_checkout",
    "ask_before_update",
    "load_existing_skill",
]


UNAVAILABLE_TOOLS: tuple[str, ...] = ("logion skills search",)


class DecisionPolicySignature(dspy.Signature):
    """Decide which action the Logion bootstrap skill should take.

    Given the user prompt, the set of installed capabilities, available
    marketplace search results, and the current policy instructions,
    produce a structured decision with action, optional search query,
    selected courses, confirmation flag, and a short reason.

    Constraints:
    - Only emit actions from the `ActionKind` enum; do not invent new
      action names or route through tools that are not yet implemented.
    - Treat any command labeled "planned" in `current_policy_text` as
      unavailable. Specifically, the following are NOT executable yet
      and must not appear in the chosen routing: logion skills search.
    - Marketplace search must go through `search_marketplace`
      (which corresponds to `logion listings search`), never through a
      planned/unimplemented command.
    - Use `ask_before_update` when the user requests an update to an
      installed capability and the new version's manifest changes
      price, permissions, required tools, or execution policy.
    """

    user_prompt: str = dspy.InputField(
        desc="The raw user prompt that triggered the skill."
    )
    installed_capabilities: str = dspy.InputField(
        desc="Comma-separated list of installed capability IDs."
    )
    marketplace_results: str = dspy.InputField(
        desc="Summary of marketplace search results or fake catalog "
        "candidates available for this query."
    )
    current_policy_text: str = dspy.InputField(
        desc="The current bootstrap policy instructions from SKILL.md."
    )

    action: ActionKind = dspy.OutputField(
        desc="The action the skill should take."
    )
    query: str = dspy.OutputField(
        desc="Optional search query for marketplace or recall lookup. "
        "Empty string if not applicable."
    )
    selected_course_ids: str = dspy.OutputField(
        desc="Comma-separated course IDs relevant to the action. "
        "Empty string if not applicable."
    )
    requires_user_confirmation: bool = dspy.OutputField(
        desc="True if the action requires explicit user confirmation "
        "before proceeding (e.g. install, paid checkout, permission "
        "expansion)."
    )
    reason: str = dspy.OutputField(
        desc="Short explanation of why this action was chosen."
    )


class DecisionPolicyModule(dspy.Module):
    """Wraps the signature into a DSPy module for optimization."""

    def __init__(self) -> None:
        super().__init__()
        self.predictor = dspy.Predict(DecisionPolicySignature)

    def forward(self, **kwargs: object) -> dspy.Prediction:
        return self.predictor(**kwargs)
