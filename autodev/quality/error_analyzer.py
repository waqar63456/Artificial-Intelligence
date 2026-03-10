"""
Error Analyzer Agent.
Analyzes error messages and identifies the root cause in the source code.
Uses LLM to understand errors and map them to specific files and lines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.core.llm import LLMManager
from autodev.infrastructure.runtime_monitor import DetectedError

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software debugger and error analyst.
Your job is to analyze error messages, identify root causes, and suggest specific fixes.

You must return a JSON object with the following structure:
{
    "root_cause": "string - clear explanation of what caused the error",
    "affected_files": [
        {
            "path": "string - file path that needs to be modified",
            "issue": "string - what's wrong in this file",
            "fix_description": "string - what needs to be changed",
            "fix_type": "string - one of: syntax, logic, import, dependency, config, type"
        }
    ],
    "suggested_commands": ["list of terminal commands that might help (e.g., install missing deps)"],
    "confidence": "string - one of: high, medium, low",
    "category": "string - one of: syntax, runtime, dependency, config, type, logic, permission, network"
}

Be specific about file paths and line numbers when possible.
Prioritize fixes - the first affected file should be the primary fix."""

ANALYSIS_PROMPT = """Analyze the following error and identify the root cause:

Error Message:
{error_message}

Stack Trace:
{stack_trace}

Source File: {source_file}
Error Source: {error_source}

Project Files Available:
{project_files}

Project Tech Stack:
{tech_stack}

Relevant Source Code:
{source_code}

Return ONLY valid JSON with your analysis."""


@dataclass
class FileFix:
    """A suggested fix for a specific file."""

    path: str
    issue: str
    fix_description: str
    fix_type: str = ""


@dataclass
class ErrorAnalysis:
    """Complete analysis of an error."""

    root_cause: str
    affected_files: list[FileFix] = field(default_factory=list)
    suggested_commands: list[str] = field(default_factory=list)
    confidence: str = "medium"
    category: str = "runtime"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorAnalysis:
        files = [
            FileFix(
                path=f.get("path", ""),
                issue=f.get("issue", ""),
                fix_description=f.get("fix_description", ""),
                fix_type=f.get("fix_type", ""),
            )
            for f in data.get("affected_files", [])
        ]
        return cls(
            root_cause=data.get("root_cause", "Unknown"),
            affected_files=files,
            suggested_commands=data.get("suggested_commands", []),
            confidence=data.get("confidence", "medium"),
            category=data.get("category", "runtime"),
        )


class ErrorAnalyzer:
    """Analyzes errors and identifies root causes."""

    def __init__(self, llm: LLMManager) -> None:
        self.llm = llm

    async def analyze(
        self,
        error: DetectedError,
        project_files: list[str],
        tech_stack: dict[str, Any],
        source_code: str = "",
    ) -> ErrorAnalysis:
        """
        Analyze a detected error and identify its root cause.

        Args:
            error: The detected error to analyze.
            project_files: List of project file paths for context.
            tech_stack: Technology stack of the project.
            source_code: Relevant source code near the error.

        Returns:
            ErrorAnalysis with root cause and suggested fixes.
        """
        logger.info("Analyzing error: %s", error.message[:100])

        prompt = ANALYSIS_PROMPT.format(
            error_message=error.message,
            stack_trace=error.stack_trace or "Not available",
            source_file=error.file_path or "Unknown",
            error_source=error.source,
            project_files="\n".join(project_files[:50]),  # Limit to 50 files
            tech_stack=str(tech_stack),
            source_code=source_code[:3000] if source_code else "Not available",
        )

        response = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        data = response.as_json()
        if data is None:
            logger.warning("Failed to parse error analysis, returning basic analysis")
            return ErrorAnalysis(
                root_cause=f"Error in {error.source}: {error.message}",
                category="runtime",
                confidence="low",
            )

        analysis = ErrorAnalysis.from_dict(data)
        logger.info(
            "Error analysis: cause=%s, confidence=%s, files=%d",
            analysis.root_cause[:80],
            analysis.confidence,
            len(analysis.affected_files),
        )
        return analysis

    async def analyze_multiple(
        self,
        errors: list[DetectedError],
        project_files: list[str],
        tech_stack: dict[str, Any],
    ) -> list[ErrorAnalysis]:
        """
        Analyze multiple errors, potentially finding common root causes.

        Args:
            errors: List of detected errors.
            project_files: Project file paths.
            tech_stack: Technology stack.

        Returns:
            List of error analyses.
        """
        if not errors:
            return []

        # Deduplicate similar errors
        unique_errors = self._deduplicate(errors)
        logger.info("Analyzing %d unique errors (from %d total)", len(unique_errors), len(errors))

        analyses = []
        for error in unique_errors:
            analysis = await self.analyze(error, project_files, tech_stack)
            analyses.append(analysis)

        return analyses

    def _deduplicate(self, errors: list[DetectedError]) -> list[DetectedError]:
        """Remove duplicate errors based on message similarity."""
        seen: set[str] = set()
        unique: list[DetectedError] = []
        for error in errors:
            # Use a normalized version of the message as key
            key = error.message.strip().lower()[:100]
            if key not in seen:
                seen.add(key)
                unique.append(error)
        return unique
