"""
Prompt Interpreter Agent.
Analyzes the user prompt and extracts project requirements including
application type, features, technologies, and constraints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.core.llm import LLMManager

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software requirements analyst.
Your job is to analyze a user's project description and extract structured requirements.

You must return a JSON object with the following structure:
{
    "project_name": "string - a suitable project name (lowercase, hyphenated)",
    "project_type": "string - one of: web, api, mobile, desktop, microservice, fullstack",
    "description": "string - a clear 1-2 sentence description of the project",
    "features": ["list of specific features the project needs"],
    "tech_preferences": {
        "frontend": "string or null - preferred frontend framework",
        "backend": "string or null - preferred backend framework",
        "database": "string or null - preferred database",
        "language": "string or null - preferred programming language",
        "other": ["list of other specified technologies"]
    },
    "constraints": ["list of constraints or non-functional requirements"],
    "entities": ["list of main data entities/models"],
    "auth_required": "boolean - whether authentication is needed",
    "realtime_required": "boolean - whether realtime features are needed",
    "complexity": "string - one of: simple, moderate, complex"
}

Be thorough in extracting features. If the user mentions any technology explicitly, capture it.
If something is not mentioned, set it to null or empty.
"""

ANALYSIS_PROMPT = """Analyze the following project description and extract structured requirements.

User Prompt:
---
{user_prompt}
---

Return ONLY valid JSON matching the specified schema. No markdown, no explanation."""


@dataclass
class ProjectRequirements:
    """Structured project requirements extracted from user prompt."""

    project_name: str = ""
    project_type: str = ""
    description: str = ""
    features: list[str] = field(default_factory=list)
    tech_preferences: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    auth_required: bool = False
    realtime_required: bool = False
    complexity: str = "moderate"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectRequirements:
        return cls(
            project_name=data.get("project_name", ""),
            project_type=data.get("project_type", ""),
            description=data.get("description", ""),
            features=data.get("features", []),
            tech_preferences=data.get("tech_preferences", {}),
            constraints=data.get("constraints", []),
            entities=data.get("entities", []),
            auth_required=data.get("auth_required", False),
            realtime_required=data.get("realtime_required", False),
            complexity=data.get("complexity", "moderate"),
        )


class PromptInterpreter:
    """Analyzes user prompts and extracts structured project requirements."""

    def __init__(self, llm: LLMManager) -> None:
        self.llm = llm

    async def analyze(self, user_prompt: str) -> ProjectRequirements:
        """
        Analyze a user prompt and extract project requirements.

        Args:
            user_prompt: The raw user description of the desired project.

        Returns:
            Structured ProjectRequirements object.
        """
        logger.info("Analyzing user prompt to extract requirements...")

        prompt = ANALYSIS_PROMPT.format(user_prompt=user_prompt)
        response = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        data = response.as_json()
        if data is None:
            logger.error("Failed to parse LLM response as JSON. Raw: %s", response.content[:500])
            raise ValueError("LLM did not return valid JSON for requirements extraction.")

        requirements = ProjectRequirements.from_dict(data)
        logger.info(
            "Extracted requirements: project=%s type=%s features=%d",
            requirements.project_name,
            requirements.project_type,
            len(requirements.features),
        )
        return requirements
