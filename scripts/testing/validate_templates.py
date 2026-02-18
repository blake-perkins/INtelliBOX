#!/usr/bin/env python3
"""
Template Validation Script for INtelliBOX

Validates that all Jinja2 templates use correct model attributes.
This catches bugs like using 'email.text_body' instead of 'email.body_text'.

Usage:
    python validate_templates.py
"""

import re
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Import models to validate against
try:
    from intellibox.models import Email, Action, Assignment
except ImportError:
    print(f"{Fore.RED}Error: Could not import INtelliBOX models")
    print(f"{Fore.YELLOW}Make sure you're in the INtelliBOX directory and the package is installed")
    sys.exit(1)


# Map template names to their expected context variables
TEMPLATE_CONTEXTS = {
    "action_detail.html": {
        "action": Action,
        "assignment": Assignment,
    },
    "email_detail.html": {
        "email": Email,
        "actions": [Action],  # List of actions
    },
    "actions.html": {
        "actions": [Action],  # List
    },
    "emails.html": {
        "emails": [Email],  # List
    },
    "report.html": {
        "report": dict,  # Generated data structure
    },
    "dashboard.html": {},  # Uses API data
}


def get_model_attributes(model_class):
    """Get all valid attributes for a SQLAlchemy model."""
    if model_class == dict or isinstance(model_class, list):
        return set()  # Skip validation for dict/list types

    attributes = set()

    # Get column attributes
    if hasattr(model_class, '__table__'):
        for column in model_class.__table__.columns:
            attributes.add(column.name)

    # Get relationship names
    if hasattr(model_class, '__mapper__'):
        for rel in model_class.__mapper__.relationships:
            attributes.add(rel.key)

    # Add common properties
    attributes.update(['id', 'created_at', 'updated_at'])

    return attributes


def extract_template_variables(template_path):
    """Extract all {{ variable.attribute }} references from template."""
    content = Path(template_path).read_text(encoding='utf-8')

    # Find all {{ ... }} and {% ... %} patterns
    var_pattern = r'\{\{[\s]*([\w\.]+)'
    control_pattern = r'\{%[\s]*(?:if|for|elif)[\s]+([\w\.]+)'

    all_refs = []
    all_refs.extend(re.findall(var_pattern, content))
    all_refs.extend(re.findall(control_pattern, content))

    # Parse into root variable and attributes
    variables = {}
    for ref in all_refs:
        parts = ref.split('.')
        root = parts[0]

        if root not in variables:
            variables[root] = set()

        # Add the attribute chain (everything after root)
        if len(parts) > 1:
            variables[root].add('.'.join(parts[1:]))

    return variables


def validate_template(template_name, template_path):
    """Validate a template against its expected context."""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}Validating: {template_name}")
    print(f"{Fore.CYAN}{'='*70}")

    if template_name not in TEMPLATE_CONTEXTS:
        print(f"{Fore.YELLOW}[!] No validation rules defined for {template_name}")
        return True

    context = TEMPLATE_CONTEXTS[template_name]
    variables = extract_template_variables(template_path)

    errors = []
    checked = []

    # Control flow and built-in variables to skip
    skip_vars = {'request', 'loop', 'super', 'self', 'range', 'namespace'}

    for var_name, attr_chains in variables.items():
        # Skip control flow variables
        if var_name in skip_vars:
            continue

        # Check if variable is in expected context
        if var_name not in context:
            print(f"{Fore.YELLOW}[!] Unknown variable: {var_name}")
            continue

        # Get the model class for this variable
        model_class = context[var_name]

        # Handle list types (e.g., List[Action])
        if isinstance(model_class, list):
            model_class = model_class[0] if model_class else None

        if not model_class or model_class == dict:
            continue  # Skip dict and list validation

        # Get valid attributes for this model
        valid_attrs = get_model_attributes(model_class)

        # Validate each attribute chain
        for attr_chain in attr_chains:
            first_attr = attr_chain.split('.')[0]

            # Check if the first attribute exists
            if first_attr and first_attr not in valid_attrs:
                errors.append({
                    'variable': var_name,
                    'attribute': first_attr,
                    'model': model_class.__name__,
                    'valid_attrs': valid_attrs
                })
            else:
                checked.append(f"{var_name}.{first_attr}")

    # Print results
    if not errors:
        print(f"{Fore.GREEN}[OK] All validations passed ({len(checked)} attributes checked)")
        return True

    # Print errors
    print(f"\n{Fore.RED}[X] {len(errors)} error(s) found:")
    for error in errors:
        print(f"\n  {Fore.RED}Error: {error['variable']}.{error['attribute']}")
        print(f"  {Fore.YELLOW}'{error['attribute']}' is not a valid attribute of {error['model']}")

    # Show valid attributes for errored models
    shown_models = set()
    for error in errors:
        model_name = error['model']
        if model_name not in shown_models:
            shown_models.add(model_name)
            print(f"\n  {Fore.CYAN}Valid attributes for {model_name}:")
            for attr in sorted(error['valid_attrs'])[:20]:  # Show first 20
                print(f"    - {attr}")
            if len(error['valid_attrs']) > 20:
                print(f"    ... and {len(error['valid_attrs']) - 20} more")

    return False


def main():
    """Validate all templates."""
    templates_dir = Path("src/intellibox/web/templates")

    if not templates_dir.exists():
        print(f"{Fore.RED}Error: Templates directory not found: {templates_dir}")
        print(f"{Fore.YELLOW}Make sure you're in the INtelliBOX root directory")
        return 1

    print(f"{Fore.CYAN}{Style.BRIGHT}INtelliBOX Template Validator")
    print(f"{Fore.CYAN}{'='*70}")

    all_valid = True
    template_count = 0

    for template_file in sorted(templates_dir.glob("*.html")):
        if template_file.name == "base.html":
            continue  # Skip base template

        template_count += 1
        valid = validate_template(template_file.name, template_file)
        if not valid:
            all_valid = False

    # Summary
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}Validation Summary")
    print(f"{Fore.CYAN}{'='*70}")
    print(f"Templates validated: {template_count}")

    if all_valid:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}[OK] ALL TEMPLATES VALID")
        print(f"{Fore.GREEN}No attribute errors found. Templates are ready for use.{Style.RESET_ALL}\n")
        return 0
    else:
        print(f"\n{Fore.RED}{Style.BRIGHT}[X] TEMPLATE VALIDATION FAILED")
        print(f"{Fore.RED}Fix the errors above before deploying.{Style.RESET_ALL}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
