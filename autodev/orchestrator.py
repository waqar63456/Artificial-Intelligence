"""
Main Orchestrator - Workflow Engine.
Implements the complete 15-step autonomous development pipeline.
Coordinates all agents and infrastructure modules to produce a working application.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autodev.agents.code_generator import CodeGenerator, GeneratedFile
from autodev.agents.project_planner import ProjectPlan, ProjectPlanner
from autodev.agents.prompt_interpreter import ProjectRequirements, PromptInterpreter
from autodev.agents.tech_selector import TechnologySelector
from autodev.core.config import PlatformConfig
from autodev.core.llm import LLMManager
from autodev.core.logger import ActionTracker, TimedOperation, setup_logging
from autodev.infrastructure.command_executor import CommandExecutor
from autodev.infrastructure.dependency_manager import DependencyManager
from autodev.infrastructure.filesystem import FileSystemManager
from autodev.infrastructure.runtime_monitor import DetectedError, RuntimeMonitor
from autodev.quality.auto_debugger import AutoDebugger
from autodev.quality.browser_agent import BrowserAgent
from autodev.quality.error_analyzer import ErrorAnalyzer
from autodev.quality.optimizer import ContinuousImprover
from autodev.quality.security_checker import SecurityChecker
from autodev.quality.testing_agent import TestingAgent

logger = logging.getLogger("autodev")


class WorkflowStep:
    """Enumeration of workflow steps."""

    RECEIVE_PROMPT = 1
    ANALYZE_REQUEST = 2
    DESIGN_ARCHITECTURE = 3
    GENERATE_STRUCTURE = 4
    CREATE_FILES = 5
    GENERATE_CODE = 6
    INSTALL_DEPS = 7
    RUN_APP = 8
    MONITOR_ERRORS = 9
    AUTO_DEBUG = 10
    BROWSER_TEST = 11
    DEBUG_LOOP = 12
    RUN_TESTS = 13
    OPTIMIZE = 14
    DELIVER = 15


@dataclass
class WorkflowState:
    """Current state of the workflow execution."""

    current_step: int = 0
    user_prompt: str = ""
    requirements: ProjectRequirements | None = None
    tech_stack: dict[str, Any] = field(default_factory=dict)
    plan: ProjectPlan | None = None
    generated_files: list[GeneratedFile] = field(default_factory=list)
    errors: list[DetectedError] = field(default_factory=list)
    debug_iterations: int = 0
    app_running: bool = False
    app_process: Any = None
    app_url: str = ""
    test_results: dict[str, Any] = field(default_factory=dict)
    security_report: dict[str, Any] = field(default_factory=dict)
    optimization_report: dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    error_message: str = ""

    @property
    def step_name(self) -> str:
        names = {
            1: "Receive Prompt",
            2: "Analyze Request",
            3: "Design Architecture",
            4: "Generate Structure",
            5: "Create Files & Folders",
            6: "Generate Code",
            7: "Install Dependencies",
            8: "Run Application",
            9: "Monitor Errors",
            10: "Auto Debug",
            11: "Browser Testing",
            12: "Debug Loop",
            13: "Run Tests",
            14: "Optimize",
            15: "Deliver",
        }
        return names.get(self.current_step, "Unknown")


class Orchestrator:
    """
    Main workflow engine that coordinates all agents and modules
    to produce a working application from a user prompt.
    """

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.tracker = ActionTracker(config.log_dir)

        # Set up logging
        setup_logging(config.log_dir, config.verbose)

        # Initialize LLM
        self.llm = LLMManager(config.llm, config.fallback_llms)

        # Initialize agents
        self.prompt_interpreter = PromptInterpreter(self.llm)
        self.project_planner = ProjectPlanner(self.llm)
        self.tech_selector = TechnologySelector(self.llm)
        self.code_generator = CodeGenerator(self.llm)

        # Infrastructure (initialized after project dir is known)
        self.executor = CommandExecutor()
        self.runtime_monitor = RuntimeMonitor()
        self.fs: FileSystemManager | None = None
        self.dep_manager: DependencyManager | None = None

        # Quality agents (initialized after fs is set)
        self.error_analyzer = ErrorAnalyzer(self.llm)
        self.auto_debugger: AutoDebugger | None = None
        self.testing_agent: TestingAgent | None = None
        self.security_checker: SecurityChecker | None = None
        self.optimizer: ContinuousImprover | None = None
        self.browser_agent: BrowserAgent | None = None

        # State
        self.state = WorkflowState()

    def _init_project_modules(self, project_dir: str) -> None:
        """Initialize modules that depend on the project directory."""
        self.fs = FileSystemManager(project_dir)
        self.dep_manager = DependencyManager(self.executor, project_dir)
        self.auto_debugger = AutoDebugger(self.llm, self.fs, self.code_generator)
        self.testing_agent = TestingAgent(self.llm, self.executor, self.fs)
        self.security_checker = SecurityChecker(self.llm, self.fs)
        self.optimizer = ContinuousImprover(self.llm, self.fs)

        if self.config.enable_browser_testing:
            self.browser_agent = BrowserAgent()

    async def run(self, user_prompt: str) -> WorkflowState:
        """
        Execute the complete autonomous development workflow.

        Args:
            user_prompt: The user's project description.

        Returns:
            WorkflowState with the final state and results.
        """
        total_start = time.time()
        self.state.user_prompt = user_prompt

        try:
            # Step 1: Receive prompt
            self._log_step(WorkflowStep.RECEIVE_PROMPT, "Received user prompt")
            logger.info("=" * 60)
            logger.info("AUTONOMOUS DEV PLATFORM - Starting new project")
            logger.info("=" * 60)
            logger.info("Prompt: %s", user_prompt[:200])

            # Step 2: Analyze request and extract features
            await self._step_analyze_request()

            # Step 3: Design software architecture (select tech + plan)
            await self._step_design_architecture()

            # Step 4 & 5: Generate project structure and create files
            await self._step_create_project_structure()

            # Step 6: Generate code
            await self._step_generate_code()

            # Step 7: Install dependencies
            await self._step_install_dependencies()

            # Step 8: Run the application
            await self._step_run_application()

            # Steps 9-12: Monitor, debug, browser test, debug loop
            await self._step_debug_loop()

            # Step 13: Run automated tests
            await self._step_run_tests()

            # Step 14: Optimize
            if self.config.enable_optimization:
                await self._step_optimize()

            # Step 15: Deliver
            await self._step_deliver()

            self.state.completed = True

        except Exception as e:
            logger.error("Workflow failed at step %d: %s", self.state.current_step, str(e))
            self.state.error_message = str(e)
            self.state.completed = False
        finally:
            # Clean up
            await self._cleanup()
            total_duration = time.time() - total_start
            logger.info(
                "Workflow %s in %.1f seconds",
                "completed" if self.state.completed else "failed",
                total_duration,
            )
            self.tracker.record(
                agent="orchestrator",
                action="workflow_complete",
                output_data={
                    "completed": self.state.completed,
                    "duration": total_duration,
                    "steps_completed": self.state.current_step,
                    "debug_iterations": self.state.debug_iterations,
                    "files_generated": len(self.state.generated_files),
                },
            )

        return self.state

    # ------------------------------------------------------------------ #
    #  Individual workflow steps                                          #
    # ------------------------------------------------------------------ #

    async def _step_analyze_request(self) -> None:
        """Step 2: Analyze the user prompt and extract requirements."""
        self._log_step(WorkflowStep.ANALYZE_REQUEST, "Analyzing request...")

        with TimedOperation(self.tracker, "prompt_interpreter", "analyze") as op:
            op.set_input({"prompt_length": len(self.state.user_prompt)})
            self.state.requirements = await self.prompt_interpreter.analyze(
                self.state.user_prompt
            )
            op.set_output({
                "project_name": self.state.requirements.project_name,
                "project_type": self.state.requirements.project_type,
                "features_count": len(self.state.requirements.features),
            })

        logger.info(
            "Requirements extracted: %s (%s) - %d features",
            self.state.requirements.project_name,
            self.state.requirements.project_type,
            len(self.state.requirements.features),
        )

    async def _step_design_architecture(self) -> None:
        """Step 3: Select technology and design architecture."""
        self._log_step(WorkflowStep.DESIGN_ARCHITECTURE, "Designing architecture...")
        assert self.state.requirements is not None

        # Select technology stack
        with TimedOperation(self.tracker, "tech_selector", "select") as op:
            self.state.tech_stack = await self.tech_selector.select(self.state.requirements)
            op.set_output({"tech_stack": self.state.tech_stack})

        logger.info("Tech stack: %s", self.state.tech_stack)

        # Create project plan
        with TimedOperation(self.tracker, "project_planner", "plan") as op:
            self.state.plan = await self.project_planner.plan(
                self.state.requirements, self.state.tech_stack
            )
            op.set_output({
                "components": len(self.state.plan.components),
                "files": len(self.state.plan.files_to_generate),
                "tasks": len(self.state.plan.tasks),
            })

        logger.info(
            "Plan: %d components, %d files, %d tasks",
            len(self.state.plan.components),
            len(self.state.plan.files_to_generate),
            len(self.state.plan.tasks),
        )

    async def _step_create_project_structure(self) -> None:
        """Steps 4-5: Create project directories and folder structure."""
        self._log_step(WorkflowStep.GENERATE_STRUCTURE, "Creating project structure...")
        assert self.state.plan is not None
        assert self.state.requirements is not None

        # Determine project directory
        project_name = self.state.requirements.project_name or "my-project"
        project_dir = str(
            Path(self.config.project.output_dir).resolve() / project_name
        )

        # Initialize project-dependent modules
        self._init_project_modules(project_dir)
        assert self.fs is not None

        # Create base directory and subdirectories
        self.fs.ensure_base_dir()
        if self.state.plan.directories:
            self.fs.create_directories(self.state.plan.directories)

        logger.info(
            "Created project at %s with %d directories",
            project_dir,
            len(self.state.plan.directories),
        )
        self.tracker.record(
            agent="filesystem",
            action="create_structure",
            output_data={
                "project_dir": project_dir,
                "directories": len(self.state.plan.directories),
            },
        )

    async def _step_generate_code(self) -> None:
        """Step 6: Generate code for all files."""
        self._log_step(WorkflowStep.GENERATE_CODE, "Generating code...")
        assert self.state.plan is not None
        assert self.state.requirements is not None
        assert self.fs is not None

        files_to_generate = self.state.plan.files_to_generate
        logger.info("Generating %d files...", len(files_to_generate))

        for i, file_spec in enumerate(files_to_generate):
            with TimedOperation(self.tracker, "code_generator", f"generate:{file_spec.path}") as op:
                try:
                    generated = await self.code_generator.generate_file(
                        file_spec=file_spec,
                        plan=self.state.plan,
                        tech_stack=self.state.tech_stack,
                        project_name=self.state.requirements.project_name,
                        features=self.state.requirements.features,
                    )
                    # Write the file
                    self.fs.write_file(generated.path, generated.content)
                    self.state.generated_files.append(generated)
                    op.set_output({"bytes": len(generated.content)})
                    logger.info(
                        "[%d/%d] Generated: %s",
                        i + 1, len(files_to_generate), file_spec.path,
                    )
                except Exception as e:
                    logger.error("Failed to generate %s: %s", file_spec.path, str(e))

        logger.info(
            "Code generation complete: %d/%d files generated",
            len(self.state.generated_files),
            len(files_to_generate),
        )

    async def _step_install_dependencies(self) -> None:
        """Step 7: Install project dependencies."""
        self._log_step(WorkflowStep.INSTALL_DEPS, "Installing dependencies...")
        assert self.dep_manager is not None

        with TimedOperation(self.tracker, "dependency_manager", "install") as op:
            # Detect and use the appropriate package manager
            pm = self.dep_manager.detect_package_manager()
            if pm:
                result = await self.dep_manager.install_all(pm)
                op.set_output({
                    "package_manager": pm,
                    "success": result.success,
                    "errors": result.errors,
                })
                if not result.success:
                    logger.warning("Dependency install issues: %s", result.errors)
                else:
                    logger.info("Dependencies installed with %s", pm)
            else:
                logger.warning("No package manager detected - skipping dependency install")

    async def _step_run_application(self) -> None:
        """Step 8: Run the application."""
        self._log_step(WorkflowStep.RUN_APP, "Running application...")

        # Determine the run command based on tech stack
        run_cmd = self._determine_run_command()
        if not run_cmd:
            logger.warning("Could not determine run command - skipping")
            return

        assert self.fs is not None
        project_dir = self.fs.get_absolute_path()

        try:
            self.state.app_process = await self.executor.run_background(
                run_cmd, cwd=project_dir
            )
            self.state.app_running = True

            # Wait for the app to start
            await asyncio.sleep(5)

            # Check if process is still running
            if self.state.app_process.returncode is not None:
                stdout, stderr = await self.executor.read_process_output(
                    self.state.app_process
                )
                self.state.app_running = False
                logger.error(
                    "Application exited immediately. stderr: %s",
                    stderr[:500],
                )
                # Add errors for debugging
                errors = self.runtime_monitor.analyze_output(
                    stdout + "\n" + stderr, "startup"
                )
                self.state.errors.extend(errors)
            else:
                logger.info("Application is running (PID=%d)", self.state.app_process.pid)
                self.state.app_url = self._determine_app_url()

        except Exception as e:
            logger.error("Failed to start application: %s", str(e))
            self.state.app_running = False

    async def _step_debug_loop(self) -> None:
        """Steps 9-12: Monitor errors, debug, browser test, repeat."""
        max_iterations = self.config.max_debug_iterations

        while self.state.debug_iterations < max_iterations:
            self.state.debug_iterations += 1
            logger.info(
                "Debug iteration %d/%d",
                self.state.debug_iterations,
                max_iterations,
            )

            # Step 9: Monitor runtime errors
            self._log_step(WorkflowStep.MONITOR_ERRORS, "Monitoring errors...")
            current_errors: list[DetectedError] = []

            if self.state.app_running and self.state.app_process:
                process_errors = await self.runtime_monitor.monitor_process(
                    self.state.app_process, duration=5.0
                )
                current_errors.extend(process_errors)

            # Step 11: Browser testing
            if (
                self.config.enable_browser_testing
                and self.browser_agent
                and self.state.app_url
                and self.state.app_running
            ):
                self._log_step(WorkflowStep.BROWSER_TEST, "Browser testing...")
                try:
                    browser_result = await self.browser_agent.test_page(
                        self.state.app_url
                    )
                    browser_errors = browser_result.to_detected_errors()
                    current_errors.extend(browser_errors)
                except Exception as e:
                    logger.warning("Browser testing failed: %s", str(e))

            # If no errors found, we're done
            if not current_errors:
                logger.info("No errors detected - application is working!")
                break

            self.state.errors.extend(current_errors)
            logger.info("Found %d errors to fix", len(current_errors))

            # Step 10: Auto debug
            self._log_step(WorkflowStep.AUTO_DEBUG, "Auto-debugging...")
            assert self.auto_debugger is not None
            assert self.fs is not None

            for error in current_errors:
                analysis = await self.error_analyzer.analyze(
                    error=error,
                    project_files=self.fs.list_files(),
                    tech_stack=self.state.tech_stack,
                )
                debug_result = await self.auto_debugger.fix_errors(
                    analysis, self.state.tech_stack
                )

                if debug_result.success:
                    logger.info("Applied fix for: %s", analysis.root_cause[:80])

                    # Execute any suggested commands
                    for cmd in debug_result.commands_executed:
                        await self.executor.run(
                            cmd, cwd=self.fs.get_absolute_path()
                        )

            # Restart the application after fixes
            if self.state.app_running and self.state.app_process:
                await self.executor.stop_background(self.state.app_process)
                self.state.app_running = False

            run_cmd = self._determine_run_command()
            if run_cmd:
                try:
                    self.state.app_process = await self.executor.run_background(
                        run_cmd, cwd=self.fs.get_absolute_path()
                    )
                    self.state.app_running = True
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error("Failed to restart: %s", str(e))

        if self.state.debug_iterations >= max_iterations:
            logger.warning(
                "Reached max debug iterations (%d). Some issues may remain.",
                max_iterations,
            )

    async def _step_run_tests(self) -> None:
        """Step 13: Generate and run automated tests."""
        self._log_step(WorkflowStep.RUN_TESTS, "Running tests...")
        assert self.testing_agent is not None
        assert self.state.plan is not None
        assert self.fs is not None

        # Generate tests for key source files
        source_files = [
            f.path for f in self.state.plan.files_to_generate
            if not any(skip in f.path for skip in ["test", "spec", "config", ".json", ".md", ".env"])
        ]

        generated_tests = []
        for src_file in source_files[:5]:  # Limit test generation
            try:
                test = await self.testing_agent.generate_unit_tests(
                    source_file=src_file,
                    plan=self.state.plan,
                    tech_stack=self.state.tech_stack,
                    features=self.state.requirements.features if self.state.requirements else [],
                )
                self.fs.write_file(test.path, test.content)
                generated_tests.append(test)
                logger.info("Generated test: %s", test.path)
            except Exception as e:
                logger.warning("Failed to generate test for %s: %s", src_file, str(e))

        # Run tests
        if generated_tests:
            test_result = await self.testing_agent.run_tests(self.state.tech_stack)
            self.state.test_results = {
                "success": test_result.success,
                "total": test_result.total_tests,
                "passed": test_result.passed,
                "failed": test_result.failed,
                "errors": test_result.errors[:10],
            }
            logger.info(
                "Test results: %d passed, %d failed",
                test_result.passed,
                test_result.failed,
            )

    async def _step_optimize(self) -> None:
        """Step 14: Security scan and code optimization."""
        self._log_step(WorkflowStep.OPTIMIZE, "Optimizing project...")

        # Security scan
        if self.config.enable_security_scan and self.security_checker:
            logger.info("Running security scan...")
            report = await self.security_checker.scan(self.state.tech_stack)
            self.state.security_report = {
                "vulnerabilities": len(report.vulnerabilities),
                "critical": report.critical_count,
                "high": report.high_count,
                "files_scanned": report.files_scanned,
            }
            logger.info(report.summary())

        # Code optimization
        if self.optimizer:
            logger.info("Running code optimization...")
            opt_report = await self.optimizer.analyze_project(self.state.tech_stack)
            self.state.optimization_report = {
                "average_quality": opt_report.average_quality_score,
                "files_analyzed": len(opt_report.analyses),
                "files_optimized": len(opt_report.files_optimized),
            }

    async def _step_deliver(self) -> None:
        """Step 15: Produce the final working application."""
        self._log_step(WorkflowStep.DELIVER, "Delivering final application...")
        assert self.fs is not None
        assert self.state.requirements is not None

        # Generate project tree
        project_tree = self.fs.get_project_tree()

        # Write run instructions
        run_instructions = self._generate_run_instructions()
        self.fs.write_file("RUN_INSTRUCTIONS.md", run_instructions)

        # Write deployment instructions
        deploy_instructions = self._generate_deploy_instructions()
        self.fs.write_file("DEPLOY_INSTRUCTIONS.md", deploy_instructions)

        # Log final summary
        logger.info("=" * 60)
        logger.info("PROJECT DELIVERY COMPLETE")
        logger.info("=" * 60)
        logger.info("Project: %s", self.state.requirements.project_name)
        logger.info("Location: %s", self.fs.get_absolute_path())
        logger.info("Files: %d", len(self.state.generated_files))
        logger.info("Debug iterations: %d", self.state.debug_iterations)
        logger.info("\nProject tree:\n%s", project_tree)

        # Session summary
        summary = self.tracker.get_summary()
        logger.info("\nSession Summary:")
        logger.info("  Total actions: %d", summary["total_actions"])
        logger.info("  Successes: %d", summary["successes"])
        logger.info("  Failures: %d", summary["failures"])
        logger.info("  Duration: %.1fs", summary["total_duration"])

    # ------------------------------------------------------------------ #
    #  Helper methods                                                     #
    # ------------------------------------------------------------------ #

    def _log_step(self, step: int, message: str) -> None:
        """Log a workflow step transition."""
        self.state.current_step = step
        logger.info("[Step %d/15] %s", step, message)

    def _determine_run_command(self) -> list[str] | str | None:
        """Determine the appropriate command to run the application."""
        if self.fs is None:
            return None

        # Check for common project files
        if self.fs.file_exists("package.json"):
            return "npm run dev"
        elif self.fs.file_exists("manage.py"):
            return ["python", "manage.py", "runserver"]
        elif self.fs.file_exists("artisan"):
            return ["php", "artisan", "serve"]
        elif self.fs.file_exists("docker-compose.yml"):
            return ["docker", "compose", "up"]
        elif self.fs.file_exists("main.py"):
            return ["python", "main.py"]
        elif self.fs.file_exists("app.py"):
            return ["python", "app.py"]
        elif self.fs.file_exists("index.js"):
            return ["node", "index.js"]
        elif self.fs.file_exists("server.js"):
            return ["node", "server.js"]
        elif self.fs.file_exists("src/index.ts"):
            return "npx ts-node src/index.ts"

        return None

    def _determine_app_url(self) -> str:
        """Determine the application URL based on tech stack."""
        tech = self.state.tech_stack
        backend = str(tech.get("backend", "")).lower()

        if "django" in backend:
            return "http://localhost:8000"
        elif "laravel" in backend or "php" in backend:
            return "http://localhost:8000"
        elif "flask" in backend:
            return "http://localhost:5000"
        elif "fastapi" in backend:
            return "http://localhost:8000"
        else:
            return "http://localhost:3000"

    def _generate_run_instructions(self) -> str:
        """Generate run instructions for the project."""
        assert self.state.requirements is not None
        assert self.state.plan is not None

        lines = [
            f"# {self.state.requirements.project_name} - Run Instructions",
            "",
            "## Prerequisites",
            "",
        ]

        tech = self.state.tech_stack
        if "node" in str(tech.get("backend", "")).lower() or "react" in str(tech.get("frontend", "")).lower():
            lines.append("- Node.js >= 18.x")
            lines.append("- npm or yarn")
        if "python" in str(tech.get("language", "")).lower():
            lines.append("- Python >= 3.10")
            lines.append("- pip")
        if "php" in str(tech.get("language", "")).lower():
            lines.append("- PHP >= 8.1")
            lines.append("- Composer")
        if "docker" in str(tech.get("containerization", "")).lower():
            lines.append("- Docker & Docker Compose")

        lines.extend([
            "",
            "## Installation",
            "",
            "```bash",
            f"cd {self.state.requirements.project_name}",
        ])

        # Add install commands
        if self.fs and self.fs.file_exists("package.json"):
            lines.append("npm install")
        if self.fs and self.fs.file_exists("requirements.txt"):
            lines.append("pip install -r requirements.txt")
        if self.fs and self.fs.file_exists("composer.json"):
            lines.append("composer install")

        lines.extend([
            "```",
            "",
            "## Running",
            "",
            "```bash",
        ])

        run_cmd = self._determine_run_command()
        if run_cmd:
            if isinstance(run_cmd, list):
                lines.append(" ".join(run_cmd))
            else:
                lines.append(run_cmd)
        else:
            lines.append("# See project-specific documentation")

        lines.extend([
            "```",
            "",
            "## Features",
            "",
        ])

        for feature in self.state.requirements.features:
            lines.append(f"- {feature}")

        return "\n".join(lines)

    def _generate_deploy_instructions(self) -> str:
        """Generate deployment instructions."""
        assert self.state.requirements is not None

        lines = [
            f"# {self.state.requirements.project_name} - Deployment Instructions",
            "",
            "## Docker Deployment",
            "",
            "```bash",
            "docker build -t {name} .".format(name=self.state.requirements.project_name),
            "docker run -p 3000:3000 {name}".format(name=self.state.requirements.project_name),
            "```",
            "",
            "## Environment Variables",
            "",
            "Create a `.env` file with the following variables:",
            "",
            "```env",
            "NODE_ENV=production",
            "PORT=3000",
            "DATABASE_URL=your_database_url",
            "```",
            "",
            "## Cloud Deployment Options",
            "",
            "- **Vercel**: `npx vercel` (for frontend / Next.js)",
            "- **Railway**: `railway up` (for full-stack)",
            "- **AWS**: Use ECS/EKS with the provided Dockerfile",
            "- **Heroku**: `git push heroku main`",
            "- **DigitalOcean App Platform**: Connect your repository",
            "",
            "## Production Checklist",
            "",
            "- [ ] Set all environment variables",
            "- [ ] Configure database connection",
            "- [ ] Enable HTTPS/SSL",
            "- [ ] Set up monitoring and logging",
            "- [ ] Configure backups",
            "- [ ] Review security settings",
        ]

        return "\n".join(lines)

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self.state.app_process:
            try:
                await self.executor.stop_background(self.state.app_process)
            except Exception:
                pass

        if self.browser_agent:
            try:
                await self.browser_agent.stop()
            except Exception:
                pass

        await self.executor.stop_all()
