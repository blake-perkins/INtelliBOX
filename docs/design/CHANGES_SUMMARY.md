# Changes Summary: Recent Assignments & Overdue Actions Fix

## Changes Implemented

### 1. Recent Assignments No Longer Shows Completed Actions
**File**: `src/intellibox/web/app.py` (line 87-92)

**Before**:
```python
recent_assignments = session.query(Assignment, Action).join(
    Action
).order_by(desc(Assignment.assigned_at)).limit(5).all()
```

**After**:
```python
recent_assignments = session.query(Assignment, Action).join(
    Action
).filter(
    Assignment.status != "completed"
).order_by(desc(Assignment.assigned_at)).limit(5).all()
```

**Result**: Completed actions only appear in "Recent Completions", not in "Recent Assignments"

---

### 2. Overdue Actions No Longer Shows Completed Actions
**File**: `src/intellibox/web/app.py` (line 75-80)

**Before**:
```python
overdue_actions = session.query(Action).outerjoin(Assignment).join(Email).filter(
    Action.due_date < today
).order_by(Action.due_date).limit(5).all()
```

**After**:
```python
overdue_actions = session.query(Action).outerjoin(Assignment).join(Email).filter(
    Action.due_date < today,
    (Assignment.id.is_(None)) | (Assignment.status != "completed")
).order_by(Action.due_date).limit(5).all()
```

**Result**: Completed overdue actions are hidden from the dashboard (they're done!)

---

## Test Results

### Test 1: Recent Assignments Separation
- ✅ No overlap between Recent Assignments and Recent Completions
- ✅ Billy's completed task only in Recent Completions
- ✅ Dashboard loads both sections correctly

### Test 2: Overdue Actions Exclusion
- ✅ Billy's completed task (due 2026-02-02) excluded from Overdue Actions
- ✅ Old behavior: 1 overdue action → New behavior: 0 overdue actions
- ✅ Completed actions properly filtered

---

## To See Changes in Browser

**IMPORTANT**: The web server needs to be restarted to pick up code changes.

1. Stop the current web server (Ctrl+C in the terminal where it's running)
2. Restart it:
   ```bash
   intellibox web --host 127.0.0.1 --port 8000
   ```

After restart, you should see:
- ⚠️ Overdue Actions: **Empty** (Billy's completed task no longer shows)
- 📋 Recent Assignments: **Empty** (Billy's completed task moved to completions)
- ✅ Recent Completions: **Shows Billy's task**

---

## Files Modified
1. `src/intellibox/web/app.py` - Dashboard query logic (2 changes)

## Test Files Created
1. `test_assignments_separation.py` - Comprehensive test for separation
2. `test_overdue_completed.py` - Verification of filtering logic
