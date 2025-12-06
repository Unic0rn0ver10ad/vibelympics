# vibanalyz TUI Architecture Guide

## Overview

The vibanalyz TUI uses a modular architecture that separates concerns into distinct layers: **Components** (View), **Actions** (Controller), and **State** (Model). This design allows features to be added independently without creating cross-dependencies.

## Architecture Layers

### 1. Components Layer (`app/components/`)

**Purpose**: Encapsulate UI widgets and provide simple, focused interfaces for updating the display.

**Pattern**: Each component wraps a Textual widget and provides helper methods.

**Key Principles**:
- Components only know about their own widget(s)
- Components do NOT know about business logic
- Components do NOT know about other components
- Components provide simple, focused methods (e.g., `write()`, `update()`, `clear()`)

**Example Components**:
- `LogDisplay` - Wraps RichLog, provides `write()`, `clear()`, `write_section()`
- `StatusBar` - Wraps Static, provides `update()`
- `InputSection` - Wraps Input, provides `get_value()`, `set_value()`, `get_package_info()`

### 2. Actions Layer (`app/actions/`)

**Purpose**: Handle specific user actions and business logic. Each action is completely independent.

**Pattern**: Each action handler:
- Takes UI components as constructor dependencies
- Contains all logic for that specific action
- Updates UI through component interfaces
- Returns results or raises exceptions
- Does NOT depend on other actions

**Key Principles**:
- One action = one file = one responsibility
- Actions are isolated - they don't call other actions
- Actions receive components, not the main app
- Actions handle their own error cases

**Example**: `AuditAction` handles audit execution and result display.

### 3. State Layer (`app/state.py`)

**Purpose**: Track application-wide state that affects UI behavior.

**Pattern**: Simple dataclass with methods to update state.

**Key Principles**:
- State is immutable-friendly (use methods to update)
- State tracks "what happened", not "how to display it"
- State is read by the main app to decide UI updates

**Example**: `AppState` tracks `has_run_audit`, `current_package`, `audit_result`.

### 4. Main App (`app/main.py`)

**Purpose**: Orchestrate components, actions, and state. Route events to appropriate handlers.

**Pattern**: Thin orchestrator that:
- Composes UI in `compose()`
- Initializes components and actions in `on_mount()`
- Routes events to action handlers
- Updates UI based on state changes

**Key Principles**:
- Main app is the ONLY place that knows about all components and actions
- Main app routes events but doesn't contain business logic
- Main app updates UI visibility/enablement based on state

## Adding New Features

### Example: Adding a "Clear" Button

**Step 1: Create the Action Handler**

Create `app/actions/clear_action.py`:

```python
"""Action handler for clearing input and log."""

from vibanalyz.app.components.input_section import InputSection
from vibanalyz.app.components.log_display import LogDisplay
from vibanalyz.app.components.status_bar import StatusBar


class ClearAction:
    """Handles clearing input and log display."""
    
    def __init__(
        self, 
        input_section: InputSection, 
        log_display: LogDisplay, 
        status_bar: StatusBar
    ):
        """Initialize with UI components."""
        self.input = input_section
        self.log = log_display
        self.status = status_bar
    
    async def execute(self) -> None:
        """Clear input and log, reset to welcome message."""
        self.input.clear()
        self.log.clear()
        self.log.write("Welcome to Vibanalyz MVP 1.0")
        self.status.update("Ready for new audit.")
```

**Step 2: Add Button to UI**

In `app/main.py`, update `compose()`:

```python
Horizontal(
    Input(placeholder="requests", id="package-input", value=self.package_name or ""),
    Button("Run audit", id="audit-button", variant="primary"),
    Button("Clear", id="clear-button", variant="default"),  # Add this
),
```

**Step 3: Register Action in Main App**

In `app/main.py`, update `on_mount()`:

```python
# Initialize actions
self.actions["audit"] = AuditAction(
    self.components["log"], self.components["status"]
)
self.actions["clear"] = ClearAction(  # Add this
    self.components["input"],
    self.components["log"],
    self.components["status"]
)
```

**Step 4: Route Button Event**

In `app/main.py`, update `on_button_pressed()`:

```python
async def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button press events."""
    if event.button.id == "audit-button":
        package_name, version = self.components["input"].get_package_info()
        await self._handle_audit(package_name, version)
    elif event.button.id == "clear-button":  # Add this
        await self.actions["clear"].execute()
        self.state.reset()  # Update state if needed
        self._update_ui_for_state()
```

**That's it!** No changes needed to `AuditAction` or other components.

## Rules for Isolation

### ✅ DO

1. **Create new action files** for each new feature
2. **Pass components as dependencies** to actions
3. **Keep actions focused** - one action, one responsibility
4. **Update state in main app** after actions complete
5. **Use component interfaces** - don't access widgets directly from actions
6. **Route events in main app** - don't have actions call other actions

### ❌ DON'T

1. **Don't import other actions** in an action file
2. **Don't access main app** from actions or components
3. **Don't put business logic** in components
4. **Don't put UI logic** in actions (use components for UI updates)
5. **Don't create circular dependencies** between actions
6. **Don't share state** between actions (use AppState in main app)

## Component Interface Guidelines

### When to Create a New Component

Create a new component when:
- You need to encapsulate a widget with helper methods
- You want to hide widget implementation details
- You need to provide a focused interface for a UI section

### Component Method Design

- **Keep methods simple** - one clear purpose
- **Use descriptive names** - `write()`, `update()`, `clear()`
- **Don't expose widget internals** - wrap, don't expose
- **Return simple types** - strings, booleans, not complex objects

## Action Handler Guidelines

### Action Constructor

Actions should receive only the components they need:

```python
# ✅ Good - receives only needed components
def __init__(self, log: LogDisplay, status: StatusBar):
    self.log = log
    self.status = status

# ❌ Bad - receives main app or other actions
def __init__(self, app: AuditApp, other_action: SomeAction):
    ...
```

### Action Execution

Actions should:
- Be async if they perform I/O or long operations
- Return results (not None) when appropriate
- Raise exceptions for errors (don't silently fail)
- Update UI through components
- Not call other actions

```python
# ✅ Good - focused, returns result
async def execute(self, package_name: str) -> AuditResult:
    self.status.update("Running...")
    result = run_pipeline(...)
    self._display_results(result)
    return result

# ❌ Bad - calls other actions, no return value
async def execute(self, package_name: str):
    await self.other_action.execute(...)  # Don't do this
    # No return value
```

## State Management Guidelines

### What Goes in AppState

- Application-level state that affects UI behavior
- State that multiple actions might need to read
- State that persists across actions

### What Doesn't Go in AppState

- Temporary variables
- UI widget references
- Action-specific state (keep in action class)

### Updating State

State should be updated in the main app after actions complete:

```python
# In main app
result = await self.actions["audit"].execute(package_name, version)
self.state.mark_audit_complete(package_name, version, result)
self._update_ui_for_state()  # React to state changes
```

## UI Updates Based on State

The `_update_ui_for_state()` method in main app should handle:
- Showing/hiding buttons based on state
- Enabling/disabling features
- Updating button labels or styles

Example:

```python
def _update_ui_for_state(self) -> None:
    """Update UI components based on current state."""
    clear_button = self.query_one("#clear-button", Button, can_raise=False)
    if clear_button and self.state.has_run_audit:
        clear_button.visible = True
    elif clear_button:
        clear_button.visible = False
```

## Testing Strategy

### Component Testing

Test components independently by mocking widgets:

```python
def test_log_display_write():
    mock_widget = Mock(spec=RichLog)
    log = LogDisplay(mock_widget)
    log.write("test")
    mock_widget.write.assert_called_once_with("test")
```

### Action Testing

Test actions independently by mocking components:

```python
def test_audit_action_execute():
    mock_log = Mock(spec=LogDisplay)
    mock_status = Mock(spec=StatusBar)
    action = AuditAction(mock_log, mock_status)
    # Test action logic
```

## Common Patterns

### Pattern 1: Simple Action (No Dependencies on Other Actions)

```python
class SimpleAction:
    def __init__(self, component1: Component1, component2: Component2):
        self.comp1 = component1
        self.comp2 = component2
    
    async def execute(self, param: str) -> Result:
        # Do work
        # Update UI through components
        return result
```

### Pattern 2: Action That Needs State Information

```python
# In main app
async def _handle_action(self):
    # Read state if needed
    if self.state.has_run_audit:
        # Do something
        pass
    
    # Execute action
    result = await self.actions["my_action"].execute()
    
    # Update state
    self.state.some_field = result.value
    self._update_ui_for_state()
```

### Pattern 3: Conditional UI Updates

```python
def _update_ui_for_state(self) -> None:
    """Update UI based on state."""
    if self.state.has_run_audit:
        # Show additional buttons/features
        clear_btn = self.query_one("#clear-button", Button, can_raise=False)
        if clear_btn:
            clear_btn.visible = True
```

## Migration Checklist

When adding a new feature:

- [ ] Create new action file in `app/actions/`
- [ ] Action receives only needed components (not other actions)
- [ ] Action is self-contained (no dependencies on other actions)
- [ ] Register action in `on_mount()`
- [ ] Route events in main app event handlers
- [ ] Update state in main app (if needed)
- [ ] Update `_update_ui_for_state()` if UI visibility changes
- [ ] Test action independently

## Anti-Patterns to Avoid

### ❌ Action Calling Another Action

```python
# ❌ BAD - creates dependency
class ActionA:
    def __init__(self, action_b: ActionB):
        self.action_b = action_b
    
    async def execute(self):
        await self.action_b.execute()  # Don't do this
```

**Solution**: Have main app coordinate multiple actions if needed.

### ❌ Component Knowing About Business Logic

```python
# ❌ BAD - component has business logic
class LogDisplay:
    def write_audit_result(self, result: AuditResult):
        if result.score > 50:  # Business logic in component
            self.widget.write("High risk!")
```

**Solution**: Keep business logic in actions, components just display.

### ❌ Action Accessing Main App

```python
# ❌ BAD - action depends on main app
class SomeAction:
    def __init__(self, app: AuditApp):
        self.app = app  # Don't do this
```

**Solution**: Pass only needed components to actions.

## Summary

The key to maintaining isolation is:

1. **Components** = View layer (display only)
2. **Actions** = Controller layer (business logic, isolated)
3. **State** = Model layer (application state)
4. **Main App** = Orchestrator (routes events, coordinates)

Each new feature should:
- Add a new action file
- Register in main app
- Route events in main app
- NOT modify existing actions
- NOT create dependencies between actions

This architecture ensures that features can be added, modified, or removed without affecting other features.

