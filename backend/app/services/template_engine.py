"""Template engine — pure ${VAR_NAME} interpolation, no I/O."""
import re
from dataclasses import dataclass, field

VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass
class RenderResult:
    content: str
    warnings: list[str] = field(default_factory=list)


def render_template(template_content: str, variables: dict[str, str]) -> RenderResult:
    """Replace ${VAR_NAME} placeholders with variable values.

    - Resolved variables are substituted in-place.
    - Unresolved placeholders are preserved as-is and added to warnings.
    """
    warnings = []
    seen_unresolved = set()

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return variables[var_name]
        if var_name not in seen_unresolved:
            seen_unresolved.add(var_name)
            warnings.append(f"Unresolved variable: ${{{var_name}}}")
        return match.group(0)  # keep original placeholder

    result = VAR_PATTERN.sub(replacer, template_content)
    return RenderResult(content=result, warnings=warnings)


def extract_variable_names(template_content: str) -> list[str]:
    """Extract all unique variable names referenced in a template."""
    return list(dict.fromkeys(VAR_PATTERN.findall(template_content)))


def count_variable_references(template_content: str, var_name: str) -> int:
    """Count how many times ${var_name} appears in the template."""
    pattern = f"${{{var_name}}}"
    return template_content.count(pattern)
