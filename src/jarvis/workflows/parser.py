"""
Workflow parser and validator.

Parses workflow definitions from YAML/JSON and validates them.
"""

import json
import re
from pathlib import Path
from typing import Any

from jarvis.core.logging import get_logger
from jarvis.workflows.models.workflow import (
    Workflow, WorkflowStep, WorkflowTrigger,
    StepType, TriggerType, StepCondition,
)

logger = get_logger("jarvis.workflows.parser")


class WorkflowParseError(Exception):
    """Error parsing workflow definition."""
    pass


class WorkflowParser:
    """
    Parser for workflow definitions.

    Supports YAML and JSON formats with variable interpolation.
    """

    # Variable pattern: ${var} or $var
    VAR_PATTERN = re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)')

    def __init__(self):
        self.logger = get_logger("jarvis.workflows.parser")

    def parse_file(self, path: str | Path) -> Workflow:
        """
        Parse workflow from a file.

        Args:
            path: Path to workflow file (YAML or JSON)

        Returns:
            Parsed Workflow object
        """
        path = Path(path)

        if not path.exists():
            raise WorkflowParseError(f"Workflow file not found: {path}")

        content = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            return self.parse_yaml(content)
        elif path.suffix == ".json":
            return self.parse_json(content)
        else:
            # Try to detect format
            content = content.strip()
            if content.startswith("{"):
                return self.parse_json(content)
            else:
                return self.parse_yaml(content)

    def parse_yaml(self, content: str) -> Workflow:
        """Parse workflow from YAML string."""
        try:
            import yaml
            data = yaml.safe_load(content)
            return self._parse_data(data)
        except ImportError:
            raise WorkflowParseError("PyYAML not installed. Install with: pip install pyyaml")
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML: {e}")

    def parse_json(self, content: str) -> Workflow:
        """Parse workflow from JSON string."""
        try:
            data = json.loads(content)
            return self._parse_data(data)
        except json.JSONDecodeError as e:
            raise WorkflowParseError(f"Invalid JSON: {e}")

    def _parse_data(self, data: dict[str, Any]) -> Workflow:
        """Parse workflow from dictionary data."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Workflow must be a dictionary")

        try:
            # Parse steps
            steps = []
            for step_data in data.get("steps", []):
                step = self._parse_step(step_data)
                steps.append(step)

            # Parse triggers
            triggers = []
            for trigger_data in data.get("triggers", []):
                trigger = self._parse_trigger(trigger_data)
                triggers.append(trigger)

            # Build workflow
            workflow = Workflow(
                id=data.get("id"),
                name=data.get("name", "Unnamed Workflow"),
                description=data.get("description"),
                steps=steps,
                triggers=triggers,
                enabled=data.get("enabled", True),
                max_concurrent_runs=data.get("max_concurrent_runs", 1),
                timeout_seconds=data.get("timeout_seconds", 3600),
                variables=data.get("variables", {}),
                env=data.get("env", {}),
                working_directory=data.get("working_directory"),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
            )

            # Validate
            errors = workflow.validate()
            if errors:
                raise WorkflowParseError(f"Workflow validation failed: {'; '.join(errors)}")

            return workflow

        except KeyError as e:
            raise WorkflowParseError(f"Missing required field: {e}")
        except ValueError as e:
            raise WorkflowParseError(f"Invalid value: {e}")

    def _parse_step(self, data: dict[str, Any]) -> WorkflowStep:
        """Parse a single workflow step."""
        if isinstance(data, str):
            # Shorthand: just a tool name or intent
            if data.startswith("@"):
                # Intent
                return WorkflowStep(
                    name=data[1:],
                    step_type=StepType.INTENT,
                    intent=data[1:],
                )
            else:
                # Tool
                return WorkflowStep(
                    name=data,
                    step_type=StepType.TOOL,
                    tool_name=data,
                )

        # Full step definition
        step_type = StepType(data.get("type", "tool"))

        # Parse condition if present
        condition = None
        if "condition" in data:
            cond_data = data["condition"]
            if isinstance(cond_data, str):
                condition = StepCondition(expression=cond_data)
            else:
                condition = StepCondition(
                    expression=cond_data.get("if", cond_data.get("expression", "")),
                    on_true=cond_data.get("then", cond_data.get("on_true")),
                    on_false=cond_data.get("else", cond_data.get("on_false")),
                )

        return WorkflowStep(
            id=data.get("id"),
            name=data.get("name", "Unnamed Step"),
            step_type=step_type,
            tool_name=data.get("tool"),
            params=data.get("params", data.get("with", {})),
            intent=data.get("intent"),
            script=data.get("script", data.get("run")),
            condition=condition,
            parallel_steps=data.get("parallel", []),
            loop_items=data.get("loop", data.get("foreach")),
            loop_variable=data.get("as", "item"),
            depends_on=self._parse_depends(data.get("depends_on", data.get("needs", []))),
            on_error=data.get("on_error", "fail"),
            retry_count=data.get("retry", data.get("retries", 0)),
            retry_delay=data.get("retry_delay", 1.0),
            timeout_seconds=data.get("timeout", 300),
            description=data.get("description"),
            tags=data.get("tags", []),
        )

    def _parse_depends(self, depends: Any) -> list[str]:
        """Parse step dependencies."""
        if not depends:
            return []
        if isinstance(depends, str):
            return [d.strip() for d in depends.split(",")]
        if isinstance(depends, list):
            return depends
        return []

    def _parse_trigger(self, data: dict[str, Any]) -> WorkflowTrigger:
        """Parse a workflow trigger."""
        if isinstance(data, str):
            # Shorthand
            if data == "manual":
                return WorkflowTrigger(trigger_type=TriggerType.MANUAL)
            elif data.startswith("cron:"):
                return WorkflowTrigger(
                    trigger_type=TriggerType.SCHEDULE,
                    schedule=data[5:].strip(),
                )
            elif data.startswith("watch:"):
                return WorkflowTrigger(
                    trigger_type=TriggerType.FILE_WATCH,
                    watch_paths=[data[6:].strip()],
                )
            else:
                return WorkflowTrigger(trigger_type=TriggerType(data))

        trigger_type = TriggerType(data.get("type", "manual"))

        return WorkflowTrigger(
            id=data.get("id"),
            trigger_type=trigger_type,
            enabled=data.get("enabled", True),
            schedule=data.get("schedule", data.get("cron")),
            timezone=data.get("timezone", "UTC"),
            watch_paths=data.get("paths", data.get("watch", [])),
            watch_patterns=data.get("patterns", ["*"]),
            watch_events=data.get("events", ["created", "modified"]),
            webhook_path=data.get("path", data.get("webhook")),
            webhook_secret=data.get("secret"),
            event_name=data.get("event"),
            event_filter=data.get("filter", {}),
            git_events=data.get("git_events", ["push"]),
            git_branches=data.get("branches", ["main"]),
        )

    def interpolate_variables(
        self,
        value: Any,
        variables: dict[str, Any],
        step_results: dict[str, dict] | None = None,
    ) -> Any:
        """
        Interpolate variables in a value.

        Supports:
        - ${var} or $var for variables
        - ${steps.step_id.result} for step results
        - ${env.VAR} for environment variables

        Args:
            value: Value to interpolate
            variables: Variable dictionary
            step_results: Results from previous steps

        Returns:
            Interpolated value
        """
        if isinstance(value, str):
            return self._interpolate_string(value, variables, step_results)
        elif isinstance(value, dict):
            return {k: self.interpolate_variables(v, variables, step_results)
                    for k, v in value.items()}
        elif isinstance(value, list):
            return [self.interpolate_variables(v, variables, step_results)
                    for v in value]
        return value

    def _interpolate_string(
        self,
        text: str,
        variables: dict[str, Any],
        step_results: dict[str, dict] | None = None,
    ) -> str:
        """Interpolate variables in a string."""
        import os

        def replacer(match):
            var_name = match.group(1) or match.group(2)

            # Check for nested access (e.g., steps.id.result)
            parts = var_name.split(".")

            if parts[0] == "steps" and step_results and len(parts) >= 2:
                # Step result access
                step_id = parts[1]
                if step_id in step_results:
                    result = step_results[step_id]
                    for part in parts[2:]:
                        if isinstance(result, dict):
                            result = result.get(part, "")
                        else:
                            break
                    return str(result)
                return ""

            elif parts[0] == "env" and len(parts) == 2:
                # Environment variable
                return os.environ.get(parts[1], "")

            else:
                # Regular variable
                result = variables
                for part in parts:
                    if isinstance(result, dict):
                        result = result.get(part, "")
                    else:
                        break
                return str(result) if result else ""

        return self.VAR_PATTERN.sub(replacer, text)

    def to_yaml(self, workflow: Workflow) -> str:
        """Convert workflow to YAML string."""
        try:
            import yaml
            return yaml.dump(workflow.to_dict(), default_flow_style=False, sort_keys=False)
        except ImportError:
            raise WorkflowParseError("PyYAML not installed")

    def to_json(self, workflow: Workflow, indent: int = 2) -> str:
        """Convert workflow to JSON string."""
        return json.dumps(workflow.to_dict(), indent=indent)


# Module-level convenience functions
_parser: WorkflowParser | None = None


def get_parser() -> WorkflowParser:
    """Get singleton workflow parser."""
    global _parser
    if _parser is None:
        _parser = WorkflowParser()
    return _parser


def parse_workflow(source: str | Path | dict) -> Workflow:
    """
    Parse a workflow from various sources.

    Args:
        source: File path, YAML/JSON string, or dictionary

    Returns:
        Parsed Workflow object
    """
    parser = get_parser()

    if isinstance(source, dict):
        return parser._parse_data(source)
    elif isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
        return parser.parse_file(source)
    elif isinstance(source, str):
        source = source.strip()
        if source.startswith("{"):
            return parser.parse_json(source)
        else:
            return parser.parse_yaml(source)
    else:
        raise WorkflowParseError(f"Invalid workflow source: {type(source)}")


__all__ = [
    "WorkflowParser",
    "WorkflowParseError",
    "get_parser",
    "parse_workflow",
]
