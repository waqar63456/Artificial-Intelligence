"""
Continuous Improvement Agent.
Refactors and optimizes code for performance, readability, and scalability.
Provides suggestions and automatic improvements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.core.llm import LLMManager
from autodev.infrastructure.filesystem import FileSystemManager

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert code reviewer and optimization specialist.
Your job is to analyze code and suggest or apply improvements for:
1. Performance - reduce unnecessary computation, optimize queries, caching
2. Readability - clear naming, documentation, consistent style
3. Scalability - proper patterns, separation of concerns, modularity
4. Best practices - error handling, logging, typing

Rules:
- Be specific about what to change and why.
- Prioritize high-impact improvements.
- Don't change behavior - only improve quality.
- Keep suggestions practical and actionable."""

ANALYZE_PROMPT = """Analyze the following code and suggest improvements:

File: {file_path}
Tech Stack: {tech_stack}

Code:
```
{source_code}
```

Return a JSON object with the following structure:
{{
    "quality_score": 0-100,
    "suggestions": [
        {{
            "type": "performance|readability|scalability|best_practice|security",
            "priority": "high|medium|low",
            "description": "string - what to improve",
            "current_code": "string - the problematic code snippet",
            "suggested_code": "string - the improved code snippet",
            "reasoning": "string - why this improvement matters"
        }}
    ],
    "summary": "string - overall assessment"
}}

Return ONLY valid JSON."""

OPTIMIZE_PROMPT = """Optimize the following code file for production readiness.

File: {file_path}
Tech Stack: {tech_stack}

Current Code:
```
{source_code}
```

Improvements to apply:
{improvements}

Return the COMPLETE optimized file content.
Preserve all functionality. Only improve quality.
Do NOT wrap in markdown code fences. Output ONLY the raw code."""


@dataclass
class Suggestion:
    """A code improvement suggestion."""

    type: str  # performance, readability, scalability, best_practice, security
    priority: str  # high, medium, low
    description: str
    current_code: str = ""
    suggested_code: str = ""
    reasoning: str = ""


@dataclass
class AnalysisResult:
    """Result of code quality analysis."""

    file_path: str
    quality_score: int = 0
    suggestions: list[Suggestion] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_dict(cls, file_path: str, data: dict[str, Any]) -> AnalysisResult:
        suggestions = [
            Suggestion(
                type=s.get("type", ""),
                priority=s.get("priority", "medium"),
                description=s.get("description", ""),
                current_code=s.get("current_code", ""),
                suggested_code=s.get("suggested_code", ""),
                reasoning=s.get("reasoning", ""),
            )
            for s in data.get("suggestions", [])
        ]
        return cls(
            file_path=file_path,
            quality_score=data.get("quality_score", 0),
            suggestions=suggestions,
            summary=data.get("summary", ""),
        )


@dataclass
class OptimizationReport:
    """Complete optimization report for the project."""

    analyses: list[AnalysisResult] = field(default_factory=list)
    files_optimized: list[str] = field(default_factory=list)
    average_quality_score: float = 0.0

    def compute_average(self) -> None:
        if self.analyses:
            self.average_quality_score = sum(
                a.quality_score for a in self.analyses
            ) / len(self.analyses)


class ContinuousImprover:
    """Analyzes and optimizes code quality."""

    def __init__(self, llm: LLMManager, fs: FileSystemManager) -> None:
        self.llm = llm
        self.fs = fs

    async def analyze_file(
        self,
        file_path: str,
        tech_stack: dict[str, Any],
    ) -> AnalysisResult:
        """
        Analyze a single file for quality improvements.

        Args:
            file_path: Path to the file to analyze.
            tech_stack: Technology stack for context.

        Returns:
            AnalysisResult with quality score and suggestions.
        """
        logger.info("Analyzing code quality: %s", file_path)

        try:
            source_code = self.fs.read_file(file_path)
        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            return AnalysisResult(file_path=file_path, summary="File not found")

        prompt = ANALYZE_PROMPT.format(
            file_path=file_path,
            tech_stack=str(tech_stack),
            source_code=source_code[:5000],
        )

        response = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        data = response.as_json()
        if data is None:
            return AnalysisResult(
                file_path=file_path,
                summary="Analysis failed - could not parse LLM response",
            )

        return AnalysisResult.from_dict(file_path, data)

    async def optimize_file(
        self,
        file_path: str,
        tech_stack: dict[str, Any],
        improvements: list[str] | None = None,
    ) -> str:
        """
        Optimize a file by applying improvements.

        Args:
            file_path: Path to the file to optimize.
            tech_stack: Technology stack.
            improvements: Specific improvements to apply. If None, auto-detect.

        Returns:
            Optimized file content.
        """
        logger.info("Optimizing file: %s", file_path)

        source_code = self.fs.read_file(file_path)

        if improvements is None:
            # First analyze to find improvements
            analysis = await self.analyze_file(file_path, tech_stack)
            improvements = [
                s.description for s in analysis.suggestions
                if s.priority in ("high", "medium")
            ]

        if not improvements:
            logger.info("No improvements needed for %s", file_path)
            return source_code

        prompt = OPTIMIZE_PROMPT.format(
            file_path=file_path,
            tech_stack=str(tech_stack),
            source_code=source_code,
            improvements="\n".join(f"- {imp}" for imp in improvements),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1,
        )

        content = self._clean_response(response.content)
        if content.strip():
            self.fs.write_file(file_path, content)
            logger.info("Optimized: %s", file_path)
            return content

        return source_code

    async def analyze_project(
        self,
        tech_stack: dict[str, Any],
        file_extensions: set[str] | None = None,
    ) -> OptimizationReport:
        """
        Analyze the entire project for quality improvements.

        Args:
            tech_stack: Technology stack.
            file_extensions: File extensions to analyze.

        Returns:
            OptimizationReport for the project.
        """
        if file_extensions is None:
            file_extensions = {".js", ".ts", ".jsx", ".tsx", ".py", ".php", ".dart"}

        all_files = self.fs.list_files()
        target_files = [
            f for f in all_files
            if any(f.endswith(ext) for ext in file_extensions)
            and "node_modules" not in f
            and ".git" not in f
            and "test" not in f.lower()
        ]

        logger.info("Analyzing %d files for quality", len(target_files))

        report = OptimizationReport()
        for file_path in target_files[:20]:  # Limit to 20 files to control LLM costs
            analysis = await self.analyze_file(file_path, tech_stack)
            report.analyses.append(analysis)

        report.compute_average()
        logger.info(
            "Project quality analysis: avg_score=%.1f, files=%d",
            report.average_quality_score,
            len(report.analyses),
        )
        return report

    async def optimize_project(
        self,
        tech_stack: dict[str, Any],
        min_quality_score: int = 70,
    ) -> OptimizationReport:
        """
        Optimize the entire project.

        Args:
            tech_stack: Technology stack.
            min_quality_score: Only optimize files below this score.

        Returns:
            OptimizationReport with results.
        """
        report = await self.analyze_project(tech_stack)

        for analysis in report.analyses:
            if analysis.quality_score < min_quality_score:
                high_priority = [
                    s.description for s in analysis.suggestions
                    if s.priority == "high"
                ]
                if high_priority:
                    await self.optimize_file(
                        analysis.file_path, tech_stack, high_priority
                    )
                    report.files_optimized.append(analysis.file_path)

        logger.info("Optimized %d files", len(report.files_optimized))
        return report

    def _clean_response(self, content: str) -> str:
        """Remove markdown code fences if present."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text
