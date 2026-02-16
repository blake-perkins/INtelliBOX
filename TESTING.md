# EmailTools Testing Strategy

## Lessons Learned

After finding multiple template bugs in production, we've developed a more rigorous testing approach.

### Problems with Initial Testing
1. ❌ Database isolation failed in pytest suite
2. ❌ Warnings masked critical failures
3. ❌ Template variables not validated against models
4. ❌ No manual testing before declaring "ready"
5. ❌ Over-reliance on automated tests

---

## Improved Testing Approach

### 1. Manual Smoke Testing (ALWAYS DO THIS FIRST)

**Before running any automated tests, manually test every page:**

```bash
# Start the server
emailtools web --host 127.0.0.1 --port 8000
```

**Test Checklist:**
- [ ] Dashboard loads and shows correct stats
- [ ] Actions list loads with data
- [ ] Click on a high priority action - detail page loads
- [ ] Click on a medium priority action - detail page loads
- [ ] Emails list loads with data
- [ ] Click on an email - detail page loads and shows body text
- [ ] Report page loads (may be slow due to AI)
- [ ] Filter actions by priority (high/medium/low)
- [ ] Filter actions by assignment status
- [ ] Check pagination works
- [ ] Verify 404 handling (visit /actions/999999)

**Expected time:** 5-10 minutes

**Why this matters:** Automated tests can lie. Real browser testing catches UI bugs immediately.

---

### 2. Template Validation Script

Before the web interface goes live, validate all templates against models:

```python
# validate_templates.py
"""Validate that all Jinja2 templates use correct model attributes."""

import re
from pathlib import Path
from emailtools.models import Email, Action, Assignment

# Map template names to their context variables
TEMPLATE_CONTEXTS = {
    "action_detail.html": {"action": Action, "assignment": Assignment},
    "email_detail.html": {"email": Email, "actions": Action},
    "actions.html": {"actions": Action},
    "emails.html": {"emails": Email},
    "report.html": {"report": dict},  # Generated data structure
    "dashboard.html": {},
}

def get_model_attributes(model_class):
    """Get all valid attributes for a SQLAlchemy model."""
    if model_class == dict:
        return set()  # Skip validation for dict types

    attributes = set()
    for attr in dir(model_class):
        if not attr.startswith('_') and attr not in ['metadata', 'registry']:
            attributes.add(attr)

    # Add relationship names
    if hasattr(model_class, '__mapper__'):
        for rel in model_class.__mapper__.relationships:
            attributes.add(rel.key)

    return attributes

def extract_template_variables(template_path):
    """Extract all {{ variable }} references from template."""
    content = Path(template_path).read_text()

    # Find all {{ ... }} patterns
    pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)'
    matches = re.findall(pattern, content)

    # Group by root variable (before first dot)
    variables = {}
    for match in matches:
        parts = match.split('.')
        root = parts[0]
        if root not in variables:
            variables[root] = []
        if len(parts) > 1:
            variables[root].append(parts[1:])

    return variables

def validate_template(template_name, template_path):
    """Validate a template against its expected context."""
    print(f"\n{'='*70}")
    print(f"Validating: {template_name}")
    print(f"{'='*70}")

    if template_name not in TEMPLATE_CONTEXTS:
        print(f"⚠️  No validation rules for {template_name}")
        return True

    context = TEMPLATE_CONTEXTS[template_name]
    variables = extract_template_variables(template_path)

    errors = []
    warnings = []

    for var_name, attributes in variables.items():
        # Skip control flow variables
        if var_name in ['request', 'loop', 'super', 'self']:
            continue

        # Check if variable is in expected context
        if var_name not in context:
            warnings.append(f"  ⚠️  Unknown variable: {var_name}")
            continue

        # Validate attributes
        model_class = context[var_name]
        valid_attrs = get_model_attributes(model_class)

        for attr_chain in attributes:
            first_attr = attr_chain[0]
            if first_attr not in valid_attrs:
                errors.append(
                    f"  ❌ {var_name}.{first_attr} - "
                    f"'{first_attr}' not in {model_class.__name__}"
                )

    # Print results
    if not errors and not warnings:
        print("✅ All validations passed")
        return True

    if warnings:
        for warning in warnings:
            print(warning)

    if errors:
        print("\n🚨 ERRORS FOUND:")
        for error in errors:
            print(error)

        # Show correct attributes
        for var_name, model_class in context.items():
            if model_class != dict:
                attrs = get_model_attributes(model_class)
                print(f"\n  Valid attributes for {var_name} ({model_class.__name__}):")
                for attr in sorted(attrs):
                    print(f"    - {attr}")

        return False

    return True

def main():
    """Validate all templates."""
    templates_dir = Path("src/emailtools/web/templates")

    print("EmailTools Template Validator")
    print("=" * 70)

    all_valid = True
    for template_file in templates_dir.glob("*.html"):
        if template_file.name == "base.html":
            continue  # Skip base template

        valid = validate_template(template_file.name, template_file)
        if not valid:
            all_valid = False

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ ALL TEMPLATES VALID")
        return 0
    else:
        print("❌ TEMPLATE VALIDATION FAILED")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

**Run before deployment:**
```bash
python validate_templates.py
```

---

### 3. Improved Integration Tests

The `validate_web_interface.py` script is actually a good approach, but needs improvements:

**Changes made:**
- ✅ Detail page errors now FAIL tests (not warnings)
- ✅ Extracts real IDs from HTML to test actual data
- ✅ Tests all critical user flows

**Additional improvements needed:**
```python
# Add these checks:
1. Verify response contains expected content (not just 200 status)
2. Test that clicking actions from different priority levels works
3. Validate that email bodies actually display
4. Check that assignment status shows correctly
```

---

### 4. Pre-Deployment Checklist

**Before pushing to production:**

1. ✅ Manual smoke test (all pages)
2. ✅ Run `validate_templates.py`
3. ✅ Run `validate_web_interface.py`
4. ✅ Check browser console for JS errors
5. ✅ Test on different screen sizes (responsive design)
6. ✅ Verify database has test data
7. ✅ Check that AI features work (if using real API)

**Only deploy if ALL checks pass.**

---

### 5. Continuous Improvement

**After each bug found in production:**

1. Add test case that would have caught it
2. Update manual test checklist
3. Improve template validator if applicable
4. Document in this file

---

## Testing Priority

**High Priority (Must Work):**
- Dashboard loads
- Actions list and filtering
- Email list
- Detail pages (action and email)
- 404 error handling

**Medium Priority (Important):**
- Report generation
- Pagination
- Assignment status display

**Low Priority (Nice to Have):**
- Auto-refresh on dashboard
- Tab switching (HTML/text email views)

---

## Common Pitfalls

### Template Variable Names
**Always check model definitions before writing templates:**

```python
# Email model has:
email.body_text  ✅
email.body_html  ✅

# NOT:
email.text_body  ❌
email.html_body  ❌
```

### Database Attributes vs. Relationships
```python
# Direct attribute:
action.priority  ✅

# Relationship (needs query):
action.email  ✅ (relationship)
action.email.subject  ✅

# Doesn't exist:
action.from_address  ❌ (use action.email.from_address)
```

### Testing with Real Data
- Automated tests should use test database
- But validation script should use REAL database
- This catches issues with actual data

---

## Quick Commands

```bash
# Manual testing
emailtools web

# Validate templates (run this script after creating it)
python validate_templates.py

# End-to-end validation
python validate_web_interface.py

# Run pytest suite (when fixed)
pytest tests/test_web_interface.py -v
```

---

## Metrics

**Target:**
- Manual smoke test: 100% pass rate
- Template validation: 0 errors
- Integration tests: 100% pass rate (17/17 tests)
- Zero 500 errors in production

**Current Status:**
- Manual testing: ✅ Passed
- Template validation: ⚠️  Script not yet created
- Integration tests: ✅ 17/17 passing
- Production errors: ✅ All fixed

---

## Next Steps

1. Create `validate_templates.py` script
2. Fix pytest database isolation
3. Add content validation to integration tests
4. Set up CI/CD to run tests automatically
