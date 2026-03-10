"""
Command-Line Interface for the Autonomous Development Platform.
Provides the main entry point for users to interact with the system.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from autodev.core.config import LLMConfig, PlatformConfig, ProjectConfig
from autodev.orchestrator import Orchestrator


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="autodev",
        description="Autonomous Software Development Platform - Build complete applications from a single prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autodev "Build a todo app with user authentication using React and Node.js"
  autodev "Create a REST API for a blog with Django and PostgreSQL"
  autodev --provider claude "Build an e-commerce platform with Next.js"
  autodev --config config.json "Build a chat application"
  autodev --output ./projects "Create a portfolio website"
        """,
    )

    # Positional argument: the project prompt
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Project description prompt. Describe what you want to build.",
    )

    # LLM configuration
    llm_group = parser.add_argument_group("LLM Configuration")
    llm_group.add_argument(
        "--provider",
        choices=["openai", "deepseek", "claude"],
        default="openai",
        help="LLM provider to use (default: openai)",
    )
    llm_group.add_argument(
        "--model",
        default="",
        help="Specific model to use (default: auto-select based on provider)",
    )
    llm_group.add_argument(
        "--api-key",
        default="",
        help="API key for the LLM provider (default: from environment variable)",
    )
    llm_group.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="LLM temperature for generation (default: 0.2)",
    )

    # Project configuration
    proj_group = parser.add_argument_group("Project Configuration")
    proj_group.add_argument(
        "--output", "-o",
        default="./output",
        help="Output directory for the generated project (default: ./output)",
    )
    proj_group.add_argument(
        "--name",
        default="",
        help="Project name (default: auto-generated from prompt)",
    )

    # Workflow configuration
    workflow_group = parser.add_argument_group("Workflow Configuration")
    workflow_group.add_argument(
        "--max-debug-iterations",
        type=int,
        default=10,
        help="Maximum auto-debug iterations (default: 10)",
    )
    workflow_group.add_argument(
        "--no-browser-test",
        action="store_true",
        help="Disable browser-based testing",
    )
    workflow_group.add_argument(
        "--no-security-scan",
        action="store_true",
        help="Disable security scanning",
    )
    workflow_group.add_argument(
        "--no-optimize",
        action="store_true",
        help="Disable code optimization",
    )

    # General options
    parser.add_argument(
        "--config", "-c",
        default="",
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--log-dir",
        default="./logs",
        help="Directory for log files (default: ./logs)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    # Interactive mode
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode (prompt will be asked if not provided)",
    )

    return parser


def build_config(args: argparse.Namespace) -> PlatformConfig:
    """Build platform configuration from CLI arguments."""
    # Start with config file if provided
    if args.config:
        config = PlatformConfig.from_file(args.config)
    else:
        config = PlatformConfig()

    # Override with CLI arguments
    config.llm = LLMConfig(
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        temperature=args.temperature,
    )
    config.project = ProjectConfig(
        name=args.name,
        output_dir=args.output,
    )
    config.max_debug_iterations = args.max_debug_iterations
    config.enable_browser_testing = not args.no_browser_test
    config.enable_security_scan = not args.no_security_scan
    config.enable_optimization = not args.no_optimize
    config.verbose = args.verbose
    config.log_dir = args.log_dir

    return config


def get_prompt_interactive() -> str:
    """Get a project prompt from the user interactively."""
    print("\n" + "=" * 60)
    print("  AUTONOMOUS SOFTWARE DEVELOPMENT PLATFORM")
    print("=" * 60)
    print()
    print("Describe the software project you want to build.")
    print("Be as detailed as possible about features, technologies,")
    print("and any specific requirements.")
    print()
    print("Examples:")
    print('  "Build a todo app with React frontend and Express backend"')
    print('  "Create a blog API with Django, PostgreSQL, and JWT auth"')
    print('  "Build a real-time chat app with Next.js and Socket.io"')
    print()

    lines: list[str] = []
    print("Enter your prompt (press Enter twice to submit):")
    print("-" * 40)

    empty_count = 0
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break

    return "\n".join(lines).strip()


async def run_async(config: PlatformConfig, prompt: str) -> int:
    """Run the orchestrator asynchronously."""
    orchestrator = Orchestrator(config)
    state = await orchestrator.run(prompt)

    if state.completed:
        print("\n" + "=" * 60)
        print("  PROJECT COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        if orchestrator.fs:
            print(f"\n  Location: {orchestrator.fs.get_absolute_path()}")
        print(f"  Files generated: {len(state.generated_files)}")
        print(f"  Debug iterations: {state.debug_iterations}")
        if state.test_results:
            print(f"  Tests: {state.test_results.get('passed', 0)} passed, "
                  f"{state.test_results.get('failed', 0)} failed")
        if state.security_report:
            print(f"  Security: {state.security_report.get('vulnerabilities', 0)} issues found")
        print("\n  See RUN_INSTRUCTIONS.md for how to run the project.")
        print("  See DEPLOY_INSTRUCTIONS.md for deployment options.")
        return 0
    else:
        print("\n" + "=" * 60)
        print("  PROJECT BUILD FAILED")
        print("=" * 60)
        print(f"\n  Failed at step: {state.step_name}")
        print(f"  Error: {state.error_message}")
        print(f"\n  Check logs in: {config.log_dir}")
        return 1


def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Get the prompt
    prompt = args.prompt
    if not prompt:
        if args.interactive or sys.stdin.isatty():
            prompt = get_prompt_interactive()
        else:
            # Read from stdin (pipe)
            prompt = sys.stdin.read().strip()

    if not prompt:
        parser.error("No project prompt provided. Use --help for usage information.")

    # Build configuration
    config = build_config(args)

    # Validate API key availability
    if not config.llm.api_key:
        import os
        env_map = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(config.llm.provider, "")
        if env_var and not os.environ.get(env_var):
            print(f"\nError: No API key found for {config.llm.provider}.")
            print(f"Set the {env_var} environment variable or use --api-key.")
            sys.exit(1)

    # Run the workflow
    print(f"\nStarting autonomous development with {config.llm.provider}...")
    print(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print()

    exit_code = asyncio.run(run_async(config, prompt))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
