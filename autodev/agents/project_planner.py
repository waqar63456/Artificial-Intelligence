"""
Project Planner Agent.
Breaks the project into development tasks and creates a step-by-step plan.
Designs the software architecture including folder structure and module layout.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.agents.prompt_interpreter import ProjectRequirements
from autodev.core.llm import LLMManager

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software architect and project planner.
Your job is to take project requirements and create a detailed development plan
including architecture, folder structure, and ordered development tasks.

You must return a JSON object with the following structure:
{
    "architecture": {
        "pattern": "string - e.g. MVC, microservices, monolith, serverless",
        "description": "string - brief architecture description",
        "components": [
            {
                "name": "string - component name",
                "type": "string - e.g. frontend, backend, database, service",
                "description": "string - what this component does",
                "technology": "string - specific technology/framework"
            }
        ]
    },
    "folder_structure": {
        "root": "string - root folder name",
        "directories": ["list of directory paths to create, relative to root"],
        "description": "string - brief description of the folder organization"
    },
    "files_to_generate": [
        {
            "path": "string - file path relative to root",
            "purpose": "string - what this file does",
            "priority": "integer - generation order (1 = first)"
        }
    ],
    "tasks": [
        {
            "id": "integer - task number",
            "name": "string - task name",
            "description": "string - what needs to be done",
            "dependencies": ["list of task ids this depends on"],
            "category": "string - one of: setup, backend, frontend, database, config, testing, deployment"
        }
    ],
    "database_schema": {
        "tables": [
            {
                "name": "string - table/collection name",
                "fields": [
                    {
                        "name": "string",
                        "type": "string",
                        "constraints": "string - e.g. primary key, not null, unique"
                    }
                ],
                "relationships": ["string - description of relationships"]
            }
        ]
    },
    "dependencies": {
        "runtime": ["list of runtime dependency package names"],
        "dev": ["list of dev dependency package names"]
    }
}

Create a thorough, production-ready plan. Include all necessary files for a working application.
Order tasks logically: setup first, then config, database, backend, frontend, testing, deployment.
"""

PLANNING_PROMPT = """Create a detailed development plan for the following project.

Project Requirements:
- Name: {project_name}
- Type: {project_type}
- Description: {description}
- Features: {features}
- Tech Stack: {tech_stack}
- Entities: {entities}
- Auth Required: {auth_required}
- Realtime Required: {realtime_required}
- Complexity: {complexity}
- Constraints: {constraints}

Return ONLY valid JSON matching the specified schema."""


@dataclass
class FileSpec:
    """Specification for a file to generate."""

    path: str
    purpose: str
    priority: int = 1


@dataclass
class TaskSpec:
    """Specification for a development task."""

    id: int
    name: str
    description: str
    dependencies: list[int] = field(default_factory=list)
    category: str = ""


@dataclass
class ComponentSpec:
    """Specification for an architecture component."""

    name: str
    type: str
    description: str
    technology: str = ""


@dataclass
class TableFieldSpec:
    """Specification for a database table field."""

    name: str
    type: str
    constraints: str = ""


@dataclass
class TableSpec:
    """Specification for a database table."""

    name: str
    fields: list[TableFieldSpec] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)


@dataclass
class ProjectPlan:
    """Complete project development plan."""

    architecture_pattern: str = ""
    architecture_description: str = ""
    components: list[ComponentSpec] = field(default_factory=list)
    root_dir: str = ""
    directories: list[str] = field(default_factory=list)
    files_to_generate: list[FileSpec] = field(default_factory=list)
    tasks: list[TaskSpec] = field(default_factory=list)
    database_tables: list[TableSpec] = field(default_factory=list)
    runtime_dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectPlan:
        arch = data.get("architecture", {})
        folder = data.get("folder_structure", {})
        db = data.get("database_schema", {})
        deps = data.get("dependencies", {})

        components = [
            ComponentSpec(**c) for c in arch.get("components", [])
        ]
        files = [
            FileSpec(**f) for f in data.get("files_to_generate", [])
        ]
        tasks = [
            TaskSpec(
                id=t.get("id", 0),
                name=t.get("name", ""),
                description=t.get("description", ""),
                dependencies=t.get("dependencies", []),
                category=t.get("category", ""),
            )
            for t in data.get("tasks", [])
        ]
        tables = []
        for t in db.get("tables", []):
            fields = [TableFieldSpec(**f) for f in t.get("fields", [])]
            tables.append(
                TableSpec(
                    name=t.get("name", ""),
                    fields=fields,
                    relationships=t.get("relationships", []),
                )
            )

        return cls(
            architecture_pattern=arch.get("pattern", ""),
            architecture_description=arch.get("description", ""),
            components=components,
            root_dir=folder.get("root", ""),
            directories=folder.get("directories", []),
            files_to_generate=sorted(files, key=lambda f: f.priority),
            tasks=tasks,
            database_tables=tables,
            runtime_dependencies=deps.get("runtime", []),
            dev_dependencies=deps.get("dev", []),
        )


class ProjectPlanner:
    """Creates detailed development plans from project requirements."""

    def __init__(self, llm: LLMManager) -> None:
        self.llm = llm

    async def plan(self, requirements: ProjectRequirements, tech_stack: dict[str, str]) -> ProjectPlan:
        """
        Generate a complete project plan from requirements.

        Args:
            requirements: Structured project requirements.
            tech_stack: Resolved technology stack.

        Returns:
            Complete ProjectPlan with architecture, files, tasks, etc.
        """
        logger.info("Generating project plan for: %s", requirements.project_name)

        prompt = PLANNING_PROMPT.format(
            project_name=requirements.project_name,
            project_type=requirements.project_type,
            description=requirements.description,
            features=", ".join(requirements.features),
            tech_stack=str(tech_stack),
            entities=", ".join(requirements.entities),
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
            logger.error("Failed to parse project plan JSON. Raw: %s", response.content[:500])
            raise ValueError("LLM did not return valid JSON for project plan.")

        plan = ProjectPlan.from_dict(data)
        logger.info(
            "Plan generated: %d components, %d files, %d tasks",
            len(plan.components),
            len(plan.files_to_generate),
            len(plan.tasks),
        )
        return plan
