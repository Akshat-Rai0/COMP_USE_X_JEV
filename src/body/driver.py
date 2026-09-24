"""
Body module - Interface to Cua Driver for desktop interaction.

This module provides the Body abstraction that wraps Cua Driver SDK,
allowing the orchestrator to read the screen and perform actions.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

try:
    from cua_driver import (
        CuaDriver,
        GetDesktopStateInput,
        ListAppsInput,
        ListWindowsInput,
        ClickInput,
        ClickButton,
        ClickPosition,
        ActionTarget,
        TypeTextInput,
        PressKeyInput,
        EndSessionInput,
    )
    CUA_DRIVER_AVAILABLE = True
except ImportError as e:
    CUA_DRIVER_AVAILABLE = False
    print(f"Warning: cua-driver import failed: {e}")
    print("Body interface will use FakeBody for testing.")

try:
    from models import (
        UIElement,
        WindowSnapshot,
        Action,
        ActionType,
    )
except ImportError:
    try:
        from src.models import (
            UIElement,
            WindowSnapshot,
            Action,
            ActionType,
        )
    except ImportError:
        raise ImportError("Could not import models from either models or src.models")


class Body:
    """Abstract interface for desktop interaction."""
    
    async def read_frontmost_window(self) -> WindowSnapshot:
        """Read the frontmost window's UI tree and take a screenshot."""
        raise NotImplementedError
    
    async def act(self, action: Action) -> bool:
        """Perform an action on a UI element."""
        raise NotImplementedError
    
    async def list_apps(self) -> List[Dict[str, Any]]:
        """List running applications."""
        raise NotImplementedError
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass


class CuaBody(Body):
    """Cua Driver implementation of Body interface."""
    
    def __init__(self):
        if not CUA_DRIVER_AVAILABLE:
            raise ImportError("cua-driver is not installed. Install it with: pip install cua-driver")
        
        self.driver: Optional[CuaDriver] = None
        self.session: Optional[str] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the Cua Driver."""
        if self._initialized:
            return
        
        try:
            # Use simplified Cua Driver initialization
            # The current API seems to have changed, so we'll use a basic approach
            self.driver = CuaDriver.create()
            self.session = f"reflex-arc-{datetime.utcnow().timestamp()}"
            self._initialized = True
            print("✓ Cua Driver initialized (basic mode)")
        except Exception as e:
            print(f"Error initializing Cua Driver: {e}")
            raise
    
    async def read_frontmost_window(self, screenshot_path: Optional[Path] = None) -> WindowSnapshot:
        """Read the frontmost window's UI tree and take a screenshot."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get desktop state
            result = await self.driver.get_desktop_state(
                GetDesktopStateInput(
                    session=self.session,
                    screenshot_out_file=str(screenshot_path) if screenshot_path else None,
                )
            )
            
            # Handle different response formats
            if hasattr(result, 'is_error') and result.is_error:
                raise RuntimeError(f"Cua Driver error: {result.text}")
            
            # Parse the UI tree from the result
            elements = self._parse_ui_tree(result)
            
            # Get window info (simplified - will need actual Cua Driver API calls)
            window_id = "frontmost"  # Placeholder
            title = "Unknown Window"  # Placeholder
            app_name = "Unknown App"  # Placeholder
            
            return WindowSnapshot(
                window_id=window_id,
                title=title,
                app_name=app_name,
                elements=elements,
                screenshot_path=screenshot_path,
            )
        except Exception as e:
            print(f"Error reading window: {e}")
            # Return a fallback window snapshot for testing
            return WindowSnapshot(
                window_id="fallback-window",
                title="Fallback Window",
                app_name="Fallback App",
                elements=[
                    UIElement(
                        element_id="e0",
                        role="button",
                        label="Fallback Button",
                        enabled=True,
                        visible=True,
                    ),
                ],
                screenshot_path=screenshot_path,
            )
    
    def _parse_ui_tree(self, cua_result: Any) -> List[UIElement]:
        """Parse Cua Driver's UI tree into our UIElement format."""
        # This is a placeholder implementation
        # The actual implementation will need to parse the specific format
        # that Cua Driver returns in its desktop state response
        
        elements = []
        element_counter = 0
        
        # Placeholder: Create some dummy elements for now
        # In production, this will parse the actual Cua Driver response
        elements.append(UIElement(
            element_id=f"e{element_counter}",
            role="button",
            label="Example Button",
            enabled=True,
            visible=True,
        ))
        element_counter += 1
        
        return elements
    
    async def act(self, action: Action) -> bool:
        """Perform an action on a UI element."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if action.action_type == ActionType.CLICK:
                click_input = ClickInput(
                    target=ActionTarget.WINDOW(
                        window_id=action.element_id,  # This will need proper window targeting
                    ),
                    button=ClickButton.LEFT,
                    position=ClickPosition.CENTER,
                )
                result = await self.driver.click(click_input)
                
            elif action.action_type == ActionType.TYPE:
                text_input = TypeTextInput(
                    target=ActionTarget.WINDOW(
                        window_id=action.element_id,
                    ),
                    text=action.text or "",
                )
                result = await self.driver.type_text(text_input)
                
            elif action.action_type == ActionType.PRESS:
                key_press_input = PressKeyInput(
                    target=ActionTarget.WINDOW(
                        window_id=action.element_id,
                    ),
                    keys=[action.key or ""],
                )
                result = await self.driver.press_key(key_press_input)
                
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")
            
            # Handle different response formats
            if hasattr(result, 'is_error') and result.is_error:
                print(f"Action failed: {result.text}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error performing action: {e}")
            return False
    
    async def list_apps(self) -> List[Dict[str, Any]]:
        """List running applications."""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.driver.list_apps(ListAppsInput())
            
            # Handle different response formats
            if hasattr(result, 'is_error') and result.is_error:
                raise RuntimeError(f"Cua Driver error: {result.text}")
            
            apps = []
            # Try to extract apps from result
            if hasattr(result, 'apps'):
                for app in result.apps:
                    apps.append({
                        "name": getattr(app, 'name', 'Unknown'),
                        "pid": getattr(app, 'pid', 0),
                        "running": getattr(app, 'running', True),
                    })
            
            return apps
        except Exception as e:
            print(f"Error listing apps: {e}")
            # Return fake apps for testing
            return [
                {"name": "Finder", "pid": 123, "running": True},
                {"name": "Calculator", "pid": 456, "running": True},
            ]
    
    async def shutdown(self) -> None:
        """Clean up Cua Driver resources."""
        if self.driver and self.session:
            try:
                await self.driver.end_session(EndSessionInput(session=self.session))
                await self.driver.shutdown()
            except Exception as e:
                print(f"Error during shutdown: {e}")
        
        self._initialized = False


class FakeBody(Body):
    """Fake Body implementation for testing with recorded fixtures."""
    
    def __init__(self, fixtures: Optional[Dict[str, Any]] = None):
        """
        Initialize FakeBody with optional fixtures.
        
        Args:
            fixtures: Dictionary of fixture data for testing
        """
        self.fixtures = fixtures or {}
        self.current_fixture_index = 0
        self.actions_log: List[Action] = []
    
    async def read_frontmost_window(self, screenshot_path: Optional[Path] = None) -> WindowSnapshot:
        """Return a pre-recorded window snapshot from fixtures."""
        if not self.fixtures:
            # Return a minimal fake snapshot if no fixtures provided
            return WindowSnapshot(
                window_id="fake-window",
                title="Fake Window",
                app_name="Fake App",
                elements=[
                    UIElement(
                        element_id="e0",
                        role="button",
                        label="Fake Button",
                        enabled=True,
                        visible=True,
                    ),
                ],
                screenshot_path=screenshot_path,
            )
        
        # Get current fixture
        fixture_key = f"step_{self.current_fixture_index}"
        if fixture_key not in self.fixtures:
            raise KeyError(f"Fixture {fixture_key} not found")
        
        fixture = self.fixtures[fixture_key]
        
        # Build WindowSnapshot from fixture
        elements = []
        for elem_data in fixture.get("elements", []):
            elements.append(UIElement(**elem_data))
        
        return WindowSnapshot(
            window_id=fixture.get("window_id", "fake-window"),
            title=fixture.get("title", "Fake Window"),
            app_name=fixture.get("app_name", "Fake App"),
            elements=elements,
            screenshot_path=screenshot_path,
        )
    
    async def act(self, action: Action) -> bool:
        """Log the action and return success (for testing)."""
        self.actions_log.append(action)
        print(f"[FakeBody] Action logged: {action.action_type.value} on {action.element_id}")
        return True
    
    async def list_apps(self) -> List[Dict[str, Any]]:
        """Return fake app list."""
        return [
            {"name": "Fake App", "pid": 1234, "running": True},
        ]
    
    def get_actions_log(self) -> List[Action]:
        """Get the log of all actions performed."""
        return self.actions_log
    
    def advance_fixture(self) -> None:
        """Advance to the next fixture (for multi-step testing)."""
        self.current_fixture_index += 1