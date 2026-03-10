"""
Testing Agent.
Automatically generates and runs tests including unit tests,
API tests, and UI interaction tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from autodev.agents.project_planner import ProjectPlan
from autodev.core.llm import LLMManager
from autodev.infrastructure.command_executor import CommandExecutor, CommandResult
from autodev.infrastructure.filesystem import FileSystemManager

logger = logging.getLogger("autodev")

SYSTEM_PROMPT = """You are an expert software test engineer.
Your job is to generate comprehensive tests for the given code.

Rules:
1. Generate only the test file content. No explanations, no markdown fences.
2. Use the appropriate testing framework for the technology stack.
3. Cover key functionality, edge cases, and error scenarios.
4. Include setup/teardown as needed.
5. Write clear test names that describe the expected behavior.
6. Mock external dependencies appropriately.

Testing frameworks to use:
- JavaScript/TypeScript: Jest or Vitest
- Python: pytest
- PHP: PHPUnit
- Flutter/Dart: flutter_test
- Rust: built-in #[test]"""

GENERATE_TESTS_PROMPT = """Generate comprehensive tests for the following source code:

File: {file_path}
Purpose: {file_purpose}

Source Code:
```
{source_code}
```

Tech Stack: {tech_stack}
Test Framework: {test_framework}

Project Features: {features}

Generate the COMPLETE test file. Include all imports and setup.
Output ONLY the raw test code, no markdown fences."""

API_TEST_PROMPT = """Generate API tests for the following endpoints:

API Endpoints:
{endpoints}

Tech Stack: {tech_stack}
Base URL: {base_url}

Generate comprehensive API tests covering:
- Success responses
- Error responses (400, 401, 404, 500)
- Request validation
- Response schema validation

Output ONLY the raw test code, no markdown fences."""


@dataclass
class TestResult:
    """Result of running tests."""

    success: bool
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    output: str = ""
    duration_seconds: float = 0.0


@dataclass
class GeneratedTest:
    """A generated test file."""

    path: str
    content: str
    test_type: str  # "unit", "api", "ui"
    source_file: str = ""


# Test framework detection and run commands
TEST_FRAMEWORKS: dict[str, dict[str, Any]] = {
    "jest": {
        "languages": ["javascript", "typescript"],
        "config_files": ["jest.config.js", "jest.config.ts"],
        "run_command": ["npx", "jest", "--verbose"],
        "test_dir": "__tests__",
        "extension": ".test.ts",
    },
    "vitest": {
        "languages": ["javascript", "typescript"],
        "config_files": ["vitest.config.ts", "vite.config.ts"],
        "run_command": ["npx", "vitest", "run"],
        "test_dir": "__tests__",
        "extension": ".test.ts",
    },
    "pytest": {
        "languages": ["python"],
        "config_files": ["pytest.ini", "pyproject.toml", "setup.cfg"],
        "run_command": ["python", "-m", "pytest", "-v"],
        "test_dir": "tests",
        "extension": "_test.py",
    },
    "phpunit": {
        "languages": ["php"],
        "config_files": ["phpunit.xml"],
        "run_command": ["./vendor/bin/phpunit"],
        "test_dir": "tests",
        "extension": "Test.php",
    },
    "flutter_test": {
        "languages": ["dart"],
        "config_files": ["pubspec.yaml"],
        "run_command": ["flutter", "test"],
        "test_dir": "test",
        "extension": "_test.dart",
    },
}


class TestingAgent:
    """Generates and runs automated tests."""

    def __init__(
        self,
        llm: LLMManager,
        executor: CommandExecutor,
        fs: FileSystemManager,
    ) -> None:
        self.llm = llm
        self.executor = executor
        self.fs = fs

    def detect_test_framework(self, tech_stack: dict[str, Any]) -> str:
        """
        Detect the appropriate test framework.

        Args:
            tech_stack: Technology stack of the project.

        Returns:
            Name of the test framework to use.
        """
        language = tech_stack.get("language", "").lower()

        if "typescript" in language or "javascript" in language:
            # Check if vitest is configured
            if self.fs.file_exists("vite.config.ts") or self.fs.file_exists("vitest.config.ts"):
                return "vitest"
            return "jest"
        elif "python" in language:
            return "pytest"
        elif "php" in language:
            return "phpunit"
        elif "dart" in language:
            return "flutter_test"

        return "jest"  # Default fallback

    async def generate_unit_tests(
        self,
        source_file: str,
        plan: ProjectPlan,
        tech_stack: dict[str, Any],
        features: list[str],
    ) -> GeneratedTest:
        """
        Generate unit tests for a source file.

        Args:
            source_file: Path to the source file to test.
            plan: Project plan for context.
            tech_stack: Technology stack.
            features: Project features.

        Returns:
            GeneratedTest with test file content.
        """
        logger.info("Generating unit tests for: %s", source_file)

        framework = self.detect_test_framework(tech_stack)
        framework_config = TEST_FRAMEWORKS.get(framework, TEST_FRAMEWORKS["jest"])

        # Read the source file
        try:
            source_code = self.fs.read_file(source_file)
        except FileNotFoundError:
            logger.error("Source file not found: %s", source_file)
            raise

        # Determine test file path
        test_dir = framework_config["test_dir"]
        extension = framework_config["extension"]
        base_name = source_file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        test_path = f"{test_dir}/{base_name}{extension}"

        prompt = GENERATE_TESTS_PROMPT.format(
            file_path=source_file,
            file_purpose=self._get_file_purpose(source_file, plan),
            source_code=source_code[:5000],
            tech_stack=str(tech_stack),
            test_framework=framework,
            features=", ".join(features),
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        content = self._clean_response(response.content)

        return GeneratedTest(
            path=test_path,
            content=content,
            test_type="unit",
            source_file=source_file,
        )

    async def generate_api_tests(
        self,
        endpoints: list[dict[str, str]],
        tech_stack: dict[str, Any],
        base_url: str = "http://localhost:3000",
    ) -> GeneratedTest:
        """
        Generate API tests for given endpoints.

        Args:
            endpoints: List of endpoint descriptions.
            tech_stack: Technology stack.
            base_url: Base URL for API calls.

        Returns:
            GeneratedTest with API test content.
        """
        logger.info("Generating API tests for %d endpoints", len(endpoints))

        framework = self.detect_test_framework(tech_stack)
        endpoints_str = "\n".join(
            f"- {e.get('method', 'GET')} {e.get('path', '/')} - {e.get('description', '')}"
            for e in endpoints
        )

        prompt = API_TEST_PROMPT.format(
            endpoints=endpoints_str,
            tech_stack=str(tech_stack),
            base_url=base_url,
        )

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        content = self._clean_response(response.content)
        framework_config = TEST_FRAMEWORKS.get(framework, TEST_FRAMEWORKS["jest"])
        test_dir = framework_config["test_dir"]
        extension = framework_config["extension"]

        return GeneratedTest(
            path=f"{test_dir}/api{extension}",
            content=content,
            test_type="api",
        )

    async def run_tests(
        self,
        tech_stack: dict[str, Any],
        test_path: str | None = None,
    ) -> TestResult:
        """
        Run tests and return results.

        Args:
            tech_stack: Technology stack to determine test runner.
            test_path: Optional specific test file to run.

        Returns:
            TestResult with pass/fail details.
        """
        framework = self.detect_test_framework(tech_stack)
        framework_config = TEST_FRAMEWORKS.get(framework, TEST_FRAMEWORKS["jest"])

        cmd = list(framework_config["run_command"])
        if test_path:
            cmd.append(test_path)

        logger.info("Running tests with %s: %s", framework, " ".join(cmd))

        result = await self.executor.run(
            cmd,
            cwd=self.fs.get_absolute_path(),
            timeout=120,
        )

        return self._parse_test_output(result, framework)

    def _parse_test_output(self, result: CommandResult, framework: str) -> TestResult:
        """Parse test runner output to extract results."""
        output = result.stdout + "\n" + result.stderr

        # Default values
        total = passed = failed = skipped = 0
        errors: list[str] = []

        if framework in ("jest", "vitest"):
            # Parse Jest/Vitest output
            import re

            match = re.search(r"Tests:\s+(\d+)\s+passed", output)
            if match:
                passed = int(match.group(1))
            match = re.search(r"Tests:\s+(\d+)\s+failed", output)
            if match:
                failed = int(match.group(1))
            total = passed + failed

        elif framework == "pytest":
            import re

            match = re.search(r"(\d+)\s+passed", output)
            if match:
                passed = int(match.group(1))
            match = re.search(r"(\d+)\s+failed", output)
            if match:
                failed = int(match.group(1))
            match = re.search(r"(\d+)\s+error", output)
            if match:
                errors.append(f"{match.group(1)} errors")
            total = passed + failed

        if not result.success:
            # Extract error messages
            for line in output.split("\n"):
                if "FAIL" in line or "Error" in line or "error" in line.lower():
                    errors.append(line.strip())

        return TestResult(
            success=result.success and failed == 0,
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors[:20],  # Limit error list
            output=output,
            duration_seconds=result.duration_seconds,
        )

    def _get_file_purpose(self, file_path: str, plan: ProjectPlan) -> str:
        """Get the purpose of a file from the project plan."""
        for f in plan.files_to_generate:
            if f.path == file_path:
                return f.purpose
        return "Part of the project"

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
