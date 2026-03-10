"""
Technology Selector Agent.
Automatically selects the best technology stack when the user doesn't specify one.
Uses project requirements, type, and features to make informed decisions.
"""

from __future__ import annotations

import logging
from typing import Any

from autodev.agents.prompt_interpreter import ProjectRequirements
from autodev.core.llm import LLMManager

logger = logging.getLogger("autodev")

# Predefined stack recommendations based on project type
DEFAULT_STACKS: dict[str, dict[str, str]] = {
    "web": {
        "frontend": "React",
        "backend": "Node.js/Express",
        "database": "PostgreSQL",
        "language": "TypeScript",
        "package_manager": "npm",
    },
    "api": {
        "backend": "Node.js/Express",
        "database": "PostgreSQL",
        "language": "TypeScript",
        "package_manager": "npm",
    },
    "fullstack": {
        "frontend": "React",
        "backend": "Node.js/Express",
        "database": "PostgreSQL",
        "language": "TypeScript",
        "package_manager": "npm",
    },
    "mobile": {
        "framework": "Flutter",
        "backend": "Node.js/Express",
        "database": "PostgreSQL",
        "language": "Dart",
        "package_manager": "pub",
    },
    "desktop": {
        "framework": "Electron",
        "frontend": "React",
        "language": "TypeScript",
        "database": "SQLite",
        "package_manager": "npm",
    },
    "microservice": {
        "backend": "Node.js/Express",
        "database": "PostgreSQL",
        "language": "TypeScript",
        "containerization": "Docker",
        "package_manager": "npm",
    },
}

SYSTEM_PROMPT = """You are an expert technology consultant.
Given project requirements, recommend the best technology stack.

Return a JSON object with the following structure:
{
    "frontend": "string or null - frontend framework/library",
    "backend": "string - backend framework",
    "database": "string - database system",
    "language": "string - primary programming language",
    "package_manager": "string - package manager to use",
    "containerization": "string or null - containerization tool",
    "additional_tools": ["list of additional tools/libraries needed"],
    "reasoning": "string - brief explanation of choices"
}

Choose technologies that:
1. Are well-suited for the project type and features
2. Have strong community support and documentation
3. Work well together as a stack
4. Are appropriate for the project complexity
"""

SELECTION_PROMPT = """Recommend the best technology stack for this project:

- Type: {project_type}
- Description: {description}
- Features: {features}
- User Tech Preferences: {tech_preferences}
- Auth Required: {auth_required}
- Realtime Required: {realtime_required}
- Complexity: {complexity}
- Constraints: {constraints}

If the user specified any technologies, include those in your recommendation.
Return ONLY valid JSON."""


class TechnologySelector:
    """Selects optimal technology stacks for projects."""

    def __init__(self, llm: LLMManager) -> None:
        self.llm = llm

    async def select(self, requirements: ProjectRequirements) -> dict[str, Any]:
        """
        Select the best technology stack for the given requirements.

        If the user has specified technologies, those are preserved.
        Missing technologies are filled in by the AI or defaults.

        Args:
            requirements: Project requirements with optional tech preferences.

        Returns:
            Complete technology stack dictionary.
        """
        logger.info("Selecting technology stack for: %s", requirements.project_type)

        # Check if user specified enough tech preferences
        prefs = requirements.tech_preferences
        has_prefs = any(
            v for k, v in prefs.items()
            if k != "other" and v
        )

        if has_prefs:
            # Use LLM to fill in gaps while respecting user preferences
            return await self._select_with_llm(requirements)
        else:
            # Use defaults based on project type, then refine with LLM
            return await self._select_with_defaults(requirements)

    async def _select_with_llm(self, requirements: ProjectRequirements) -> dict[str, Any]:
        """Use LLM to select stack, respecting user preferences."""
        prompt = SELECTION_PROMPT.format(
            project_type=requirements.project_type,
            description=requirements.description,
            features=", ".join(requirements.features),
            tech_preferences=str(requirements.tech_preferences),
            auth_required=requirements.auth_required,
            realtime_required=requirements.realtime_required,
            complexity=requirements.complexity,
            constraints=", ".join(requirements.constraints),
        )

        response = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        data = response.as_json()
        if data is None:
            logger.warning("LLM tech selection failed, using defaults")
            return self._get_defaults(requirements.project_type)

        logger.info("Tech stack selected: %s", data)
        return data

    async def _select_with_defaults(self, requirements: ProjectRequirements) -> dict[str, Any]:
        """Start with defaults and optionally refine with LLM."""
        defaults = self._get_defaults(requirements.project_type)

        # If realtime is required, add WebSocket support
        if requirements.realtime_required:
            defaults["additional_tools"] = defaults.get("additional_tools", [])
            defaults["additional_tools"].append("Socket.io")

        # If auth is required, add auth library
        if requirements.auth_required:
            defaults["additional_tools"] = defaults.get("additional_tools", [])
            defaults["additional_tools"].append("JWT/Passport.js")

        logger.info("Using default tech stack for %s: %s", requirements.project_type, defaults)
        return defaults

    def _get_defaults(self, project_type: str) -> dict[str, Any]:
        """Get default stack for a project type."""
        stack = DEFAULT_STACKS.get(project_type, DEFAULT_STACKS["web"]).copy()
        stack["additional_tools"] = []
        stack["reasoning"] = f"Default recommended stack for {project_type} projects"
        return stack
