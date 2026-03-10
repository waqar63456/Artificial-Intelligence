"""
Code Generation Engine.
Connects with LLM APIs to generate code for each file in the project plan.
Handles context-aware generation, respecting architecture and dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from autodev.agents.project_planner import FileSpec, ProjectPlan
from autodev.core.llm import LLMManager

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software developer and code generator.
Your job is to generate production-quality code for specific files in a software project.

Rules:
1. Generate ONLY the code content for the requested file. No explanations, no markdown.
2. Follow best practices for the given technology/framework.
3. Include all necessary imports and dependencies.
4. Write clean, well-structured, documented code.
5. Handle errors appropriately.
6. Follow security best practices (parameterized queries, input validation, etc.).
7. Make the code production-ready, not just a prototype.

Do NOT wrap the code in markdown code fences. Output ONLY the raw file content."""

GENERATION_PROMPT = """Generate the complete code for the following file:

Project: {project_name}
Architecture: {architecture}
Tech Stack: {tech_stack}

File: {file_path}
Purpose: {file_purpose}

Project Context:
- Components: {components}
- Database Tables: {tables}
- Features: {features}

Previously Generated Files (for context):
{context_files}

Dependencies available: {dependencies}

Generate the COMPLETE file content. Include all imports, proper error handling, and documentation.
Output ONLY the raw code, no markdown fences."""

BATCH_GENERATION_PROMPT = """Generate complete code for multiple files in this project.

Project: {project_name}
Architecture: {architecture}
Tech Stack: {tech_stack}

Files to generate:
{file_list}

Project Context:
- Components: {components}
- Database Tables: {tables}
- Features: {features}

Dependencies available: {dependencies}

Return a JSON object where keys are file paths and values are the complete file contents as strings.
Example: {{"src/index.ts": "import express from 'express';\\n..."}}

Generate production-quality code for ALL files. Include all imports and proper error handling."""


@dataclass
class GeneratedFile:
    """A generated code file."""

    path: str
    content: str
    purpose: str = ""


class CodeGenerator:
    """Generates code for project files using LLM APIs."""

    def __init__(self, llm: LLMManager) -> None:
        self.llm = llm
        self._generated: dict[str, str] = {}  # path -> content cache

    async def generate_file(
        self,
        file_spec: FileSpec,
        plan: ProjectPlan,
        tech_stack: dict[str, Any],
        project_name: str,
        features: list[str],
    ) -> GeneratedFile:
        """
        Generate code for a single file.

        Args:
            file_spec: Specification of the file to generate.
            plan: The complete project plan for context.
            tech_stack: The technology stack being used.
            project_name: Name of the project.
            features: List of project features.

        Returns:
            GeneratedFile with the generated code.
        """
        logger.info("Generating code for: %s", file_spec.path)

        # Build context from previously generated files
        context = self._build_context()

        # Format component and table info
        components_str = ", ".join(
            f"{c.name} ({c.technology})" for c in plan.components
        )
        tables_str = ", ".join(
            f"{t.name} ({', '.join(f.name for f in t.fields)})"
            for t in plan.database_tables
        )

        prompt = GENERATION_PROMPT.format(
            project_name=project_name,
            architecture=plan.architecture_pattern,
            tech_stack=str(tech_stack),
            file_path=file_spec.path,
            file_purpose=file_spec.purpose,
            components=components_str or "N/A",
            tables=tables_str or "N/A",
            features=", ".join(features),
            context_files=context,
            dependencies=", ".join(plan.runtime_dependencies + plan.dev_dependencies),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        content = self._clean_response(response.content)
        self._generated[file_spec.path] = content

        logger.info("Generated %d bytes for %s", len(content), file_spec.path)
        return GeneratedFile(
            path=file_spec.path,
            content=content,
            purpose=file_spec.purpose,
        )

    async def generate_batch(
        self,
        file_specs: list[FileSpec],
        plan: ProjectPlan,
        tech_stack: dict[str, Any],
        project_name: str,
        features: list[str],
    ) -> list[GeneratedFile]:
        """
        Generate code for multiple files in a single LLM call.
        More efficient for smaller files that share context.

        Args:
            file_specs: List of file specifications.
            plan: The complete project plan.
            tech_stack: The technology stack.
            project_name: Project name.
            features: Project features.

        Returns:
            List of GeneratedFile objects.
        """
        logger.info("Batch generating %d files", len(file_specs))

        file_list = "\n".join(
            f"- {f.path}: {f.purpose}" for f in file_specs
        )
        components_str = ", ".join(
            f"{c.name} ({c.technology})" for c in plan.components
        )
        tables_str = ", ".join(
            f"{t.name} ({', '.join(f.name for f in t.fields)})"
            for t in plan.database_tables
        )

        prompt = BATCH_GENERATION_PROMPT.format(
            project_name=project_name,
            architecture=plan.architecture_pattern,
            tech_stack=str(tech_stack),
            file_list=file_list,
            components=components_str or "N/A",
            tables=tables_str or "N/A",
            features=", ".join(features),
            dependencies=", ".join(plan.runtime_dependencies + plan.dev_dependencies),
        )

        response = await self.llm.generate_structured(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        data = response.as_json()
        if data is None:
            logger.warning("Batch generation failed, falling back to individual generation")
            results = []
            for spec in file_specs:
                generated = await self.generate_file(
                    spec, plan, tech_stack, project_name, features
                )
                results.append(generated)
            return results

        results = []
        for spec in file_specs:
            content = data.get(spec.path, "")
            if isinstance(content, str):
                content = self._clean_response(content)
                self._generated[spec.path] = content
                results.append(GeneratedFile(
                    path=spec.path,
                    content=content,
                    purpose=spec.purpose,
                ))
            else:
                logger.warning("No content generated for %s in batch", spec.path)

        return results

    async def regenerate_file(
        self,
        file_path: str,
        current_content: str,
        error_message: str,
        plan: ProjectPlan,
        tech_stack: dict[str, Any],
    ) -> GeneratedFile:
        """
        Regenerate a file to fix an error.

        Args:
            file_path: Path of the file to fix.
            current_content: Current file content with the error.
            error_message: The error that needs to be fixed.
            plan: Project plan for context.
            tech_stack: Technology stack.

        Returns:
            GeneratedFile with fixed code.
        """
        logger.info("Regenerating %s to fix error: %s", file_path, error_message[:100])

        prompt = f"""Fix the following code file that has an error.

File: {file_path}

Current Code:
```
{current_content}
```

Error:
{error_message}

Tech Stack: {tech_stack}

Fix the error and return the COMPLETE corrected file content.
Do NOT wrap in markdown code fences. Output ONLY the raw code."""

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1,
        )

        content = self._clean_response(response.content)
        self._generated[file_path] = content

        return GeneratedFile(
            path=file_path,
            content=content,
            purpose="error fix",
        )

    def _build_context(self) -> str:
        """Build context string from previously generated files."""
        if not self._generated:
            return "None yet."
        context_parts = []
        for path, content in list(self._generated.items())[-5:]:
            # Only include a summary to stay within token limits
            lines = content.split("\n")
            preview = "\n".join(lines[:20])
            if len(lines) > 20:
                preview += f"\n... ({len(lines) - 20} more lines)"
            context_parts.append(f"--- {path} ---\n{preview}")
        return "\n\n".join(context_parts)

    def _clean_response(self, content: str) -> str:
        """Remove markdown code fences if present."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # Remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove closing fence
            text = "\n".join(lines)
        return text

    def clear_cache(self) -> None:
        """Clear the generated files cache."""
        self._generated.clear()
