"""
Auto Debugger Agent.
Automatically fixes errors by modifying the relevant code files and reruns the application.
Coordinates with the Error Analyzer and Code Generator to produce fixes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.agents.code_generator import CodeGenerator, GeneratedFile
from autodev.core.llm import LLMManager
from autodev.infrastructure.filesystem import FileSystemManager
from autodev.quality.error_analyzer import ErrorAnalysis, FileFix

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software debugger.
Your job is to fix code files based on error analysis.

Rules:
1. Output ONLY the complete fixed file content. No explanations, no markdown fences.
2. Preserve all existing functionality - only fix the identified issue.
3. Maintain the same code style and conventions.
4. Add proper error handling if the fix requires it.
5. Make minimal changes needed to fix the issue.
6. Ensure all imports are correct after the fix."""

FIX_PROMPT = """Fix the following code file based on the error analysis:

File: {file_path}
Issue: {issue}
Fix Required: {fix_description}
Error Category: {error_category}
Root Cause: {root_cause}

Current File Content:
```
{current_content}
```

Other Context:
{context}

Return ONLY the complete fixed file content. No markdown fences, no explanations."""


@dataclass
class DebugResult:
    """Result of a debugging attempt."""

    success: bool
    fixed_files: list[GeneratedFile] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    remaining_errors: list[str] = field(default_factory=list)
    iteration: int = 0


class AutoDebugger:
    """Automatically fixes code errors."""

    def __init__(
        self,
        llm: LLMManager,
        fs: FileSystemManager,
        code_gen: CodeGenerator,
    ) -> None:
        self.llm = llm
        self.fs = fs
        self.code_gen = code_gen
        self._fix_history: list[dict[str, str]] = []

    async def fix_errors(
        self,
        analysis: ErrorAnalysis,
        tech_stack: dict[str, Any],
    ) -> DebugResult:
        """
        Apply fixes for analyzed errors.

        Args:
            analysis: Error analysis with affected files and fix descriptions.
            tech_stack: Technology stack for context.

        Returns:
            DebugResult indicating what was fixed.
        """
        logger.info(
            "Auto-debugging: %s (confidence=%s)",
            analysis.root_cause[:80],
            analysis.confidence,
        )

        fixed_files: list[GeneratedFile] = []
        commands: list[str] = []

        # Fix each affected file
        for file_fix in analysis.affected_files:
            try:
                generated = await self._fix_file(file_fix, analysis, tech_stack)
                if generated:
                    # Write the fixed file
                    self.fs.write_file(generated.path, generated.content)
                    fixed_files.append(generated)
                    logger.info("Fixed file: %s", generated.path)
            except Exception as e:
                logger.error("Failed to fix %s: %s", file_fix.path, str(e))

        # Execute any suggested commands (e.g., installing missing deps)
        for cmd in analysis.suggested_commands:
            commands.append(cmd)
            logger.info("Suggested command: %s", cmd)

        # Record fix history
        self._fix_history.append({
            "root_cause": analysis.root_cause,
            "files_fixed": [f.path for f in fixed_files],
            "confidence": analysis.confidence,
        })

        return DebugResult(
            success=len(fixed_files) > 0,
            fixed_files=fixed_files,
            commands_executed=commands,
            remaining_errors=[],
        )

    async def _fix_file(
        self,
        file_fix: FileFix,
        analysis: ErrorAnalysis,
        tech_stack: dict[str, Any],
    ) -> GeneratedFile | None:
        """
        Fix a single file based on the fix specification.

        Args:
            file_fix: Fix specification for the file.
            analysis: Full error analysis for context.
            tech_stack: Technology stack.

        Returns:
            GeneratedFile with fixed content, or None if fix failed.
        """
        # Read current file content
        try:
            current_content = self.fs.read_file(file_fix.path)
        except FileNotFoundError:
            logger.warning("File not found for fixing: %s", file_fix.path)
            # If file doesn't exist, generate it from scratch
            return await self._generate_missing_file(file_fix, tech_stack)

        # Build context from recent fixes
        context = self._build_fix_context()

        prompt = FIX_PROMPT.format(
            file_path=file_fix.path,
            issue=file_fix.issue,
            fix_description=file_fix.fix_description,
            error_category=analysis.category,
            root_cause=analysis.root_cause,
            current_content=current_content,
            context=context,
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1,
        )

        content = self._clean_response(response.content)
        if not content.strip():
            logger.warning("Empty fix generated for %s", file_fix.path)
            return None

        return GeneratedFile(
            path=file_fix.path,
            content=content,
            purpose=f"fix: {file_fix.issue[:50]}",
        )

    async def _generate_missing_file(
        self,
        file_fix: FileFix,
        tech_stack: dict[str, Any],
    ) -> GeneratedFile | None:
        """Generate a missing file based on fix requirements."""
        prompt = f"""Generate a complete file that was missing from the project.

File: {file_fix.path}
Why it's needed: {file_fix.issue}
What it should contain: {file_fix.fix_description}
Tech Stack: {tech_stack}

Generate the COMPLETE file content. No markdown fences."""

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        content = self._clean_response(response.content)
        if not content.strip():
            return None

        return GeneratedFile(
            path=file_fix.path,
            content=content,
            purpose=f"generated missing file: {file_fix.path}",
        )

    def _build_fix_context(self) -> str:
        """Build context from recent fix history."""
        if not self._fix_history:
            return "No previous fixes in this session."

        parts = []
        for fix in self._fix_history[-5:]:
            parts.append(
                f"- Fixed: {fix['root_cause'][:60]} in {', '.join(fix['files_fixed'])}"
            )
        return "Previous fixes:\n" + "\n".join(parts)

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

    def get_fix_history(self) -> list[dict[str, str]]:
        """Get the history of all fixes applied."""
        return self._fix_history.copy()

    def clear_history(self) -> None:
        """Clear fix history."""
        self._fix_history.clear()
