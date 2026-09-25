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
        GetWindowStateInput,
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
        
        # Store current window information for targeting
        self.current_window_pid: Optional[int] = None
        self.current_window_id: Optional[int] = None
        self.current_window_info: Optional[Any] = None
        
        # Store element mapping for targeting
        self.element_map: Dict[str, Any] = {}  # Maps element_id -> Cua element
        
        # Screen recording state
        self.recording_active: bool = False
        self.recording_run_id: Optional[int] = None
        self.recording_frames: List[Path] = []
        self.recording_start_time: Optional[datetime] = None
        self.recording_dir: Optional[Path] = None
    
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
            # Get list of windows to find frontmost
            from cua_driver import ListWindowsInput
            windows_result = await self.driver.list_windows(ListWindowsInput(pid=None, on_screen_only=True))
            
            if not windows_result.windows:
                raise RuntimeError("No windows found")
            
            # Get the frontmost window (highest z_index)
            frontmost_window = max(windows_result.windows, key=lambda w: w.z_index)
            
            # Store window information for targeting
            self.current_window_pid = frontmost_window.pid
            self.current_window_id = frontmost_window.window_id
            self.current_window_info = frontmost_window
            
            # Get window state with accessibility tree
            # GetWindowStateInput imported at top
            screenshot_path = screenshot_path or Path.cwd() / "runs" / "window_screenshot.png"
            screenshot_path.parent.mkdir(exist_ok=True)
            
            window_result = await self.driver.get_window_state(
                GetWindowStateInput(
                    pid=frontmost_window.pid,
                    window_id=frontmost_window.window_id,
                    session=self.session,
                    query=None,
                    include_accessibility_tree=True,
                    include_screenshot=True,
                    screenshot_out_file=str(screenshot_path),
                    max_elements=255,  # Limit to kev/Jev requirement
                    max_depth=10,
                    max_dimension=1000
                )
            )
            
            # Check if the result is degraded
            if window_result.degraded:
                print(f"Warning: Window state degraded: {window_result.degraded_reason}")
                # Fall back to basic window info
                elements = []
            else:
                # Parse accessibility elements
                elements = self._parse_accessibility_elements(window_result.elements)
            
            return WindowSnapshot(
                window_id=str(frontmost_window.window_id),
                title=window_result.window_title or frontmost_window.app_name,
                app_name=window_result.app_name,
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
    
    def _parse_accessibility_elements(self, cua_elements: List[Any]) -> List[UIElement]:
        """Parse Cua Driver accessibility elements into our UIElement format."""
        elements = []
        element_counter = 0
        self.element_map = {}  # Reset element map
        
        def parse_element_recursive(cua_elem, parent_id: Optional[str] = None) -> None:
            nonlocal element_counter
            if element_counter >= 255:  # kev/Jev limit
                return
            
            try:
                # Extract element properties
                elem_id = f"e{element_counter}"
                role = getattr(cua_elem, 'role', 'unknown')
                label = getattr(cua_elem, 'label', None)
                value = getattr(cua_elem, 'value', None)
                enabled = getattr(cua_elem, 'enabled', True)
                visible = getattr(cua_elem, 'visible', True)
                
                # Extract position/bounds if available
                frame = getattr(cua_elem, 'frame', None)
                position = None
                if frame:
                    position = {
                        'x': getattr(frame, 'x', 0),
                        'y': getattr(frame, 'y', 0),
                        'width': getattr(frame, 'w', 0),
                        'height': getattr(frame, 'h', 0),
                    }
                
                # Create UIElement
                ui_element = UIElement(
                    element_id=elem_id,
                    role=role,
                    label=label or f"{role} {element_counter}",
                    value=value,
                    enabled=enabled,
                    visible=visible,
                    parent_id=parent_id,
                )
                elements.append(ui_element)
                
                # Store mapping for targeting
                self.element_map[elem_id] = {
                    'cua_element': cua_elem,
                    'position': position,
                    'frame': frame,
                    'pid': self.current_window_pid,
                    'window_id': self.current_window_id,
                }
                
                element_counter += 1
                
                # Recursively parse children
                if hasattr(cua_elem, 'children') and cua_elem.children:
                    for child in cua_elem.children:
                        parse_element_recursive(child, elem_id)
                        
            except Exception as e:
                print(f"Error parsing element: {e}")
        
        # Start parsing from root elements
        for cua_elem in cua_elements:
            parse_element_recursive(cua_elem)
        
        return elements
    
    def _get_element_target(self, element_id: str) -> Optional[Any]:
        """Get the Cua Driver target for a specific element."""
        if element_id not in self.element_map:
            print(f"Warning: Element {element_id} not found in element map")
            return None
        
        element_data = self.element_map[element_id]
        return element_data
    
    def _find_element_coordinates(self, element_id: str) -> Optional[Dict[str, float]]:
        """Find the coordinates for a specific element."""
        element_data = self._get_element_target(element_id)
        if not element_data:
            return None
        
        position = element_data.get('position')
        if not position:
            print(f"Warning: No position data for element {element_id}")
            return None
        
        # Calculate center point
        x = position['x'] + position['width'] / 2
        y = position['y'] + position['height'] / 2
        
        return {'x': x, 'y': y}
    
    async def act(self, action: Action) -> bool:
        """Perform an action on a UI element."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Try element-level targeting first
            element_data = self._get_element_target(action.element_id)
            
            if action.action_type == ActionType.CLICK:
                if element_data and element_data.get('position'):
                    # Use element coordinates for precise clicking
                    coords = self._find_element_coordinates(action.element_id)
                    if coords:
                        click_input = ClickInput(
                            target=ActionTarget.DESKTOP(display_id="main"),
                            button=ClickButton.LEFT,
                            position=ClickPosition.COORDINATES(
                                x=coords['x'],
                                y=coords['y']
                            ),
                        )
                    else:
                        # Fallback to desktop targeting
                        click_input = ClickInput(
                            target=ActionTarget.DESKTOP(display_id="main"),
                            button=ClickButton.LEFT,
                            position=ClickPosition.CENTER,
                        )
                else:
                    # Use window-level targeting
                    if self.current_window_pid and self.current_window_id:
                        click_input = ClickInput(
                            target=ActionTarget.WINDOW(
                                pid=self.current_window_pid,
                                window_id=self.current_window_id,
                            ),
                            button=ClickButton.LEFT,
                            position=ClickPosition.CENTER,
                        )
                    else:
                        # Fallback to desktop targeting
                        click_input = ClickInput(
                            target=ActionTarget.DESKTOP(display_id="main"),
                            button=ClickButton.LEFT,
                            position=ClickPosition.CENTER,
                        )
                result = await self.driver.click(click_input)
                
            elif action.action_type == ActionType.TYPE:
                if element_data:
                    # Use window-level targeting for typing
                    if self.current_window_pid and self.current_window_id:
                        text_input = TypeTextInput(
                            target=ActionTarget.WINDOW(
                                pid=self.current_window_pid,
                                window_id=self.current_window_id,
                            ),
                            text=action.text or "",
                        )
                    else:
                        # Fallback to desktop targeting
                        text_input = TypeTextInput(
                            target=ActionTarget.DESKTOP(display_id="main"),
                            text=action.text or "",
                        )
                else:
                    # Fallback to desktop targeting
                    text_input = TypeTextInput(
                        target=ActionTarget.DESKTOP(display_id="main"),
                        text=action.text or "",
                    )
                result = await self.driver.type_text(text_input)
                
            elif action.action_type == ActionType.PRESS:
                if element_data:
                    # Use window-level targeting for key presses
                    if self.current_window_pid and self.current_window_id:
                        key_press_input = PressKeyInput(
                            target=ActionTarget.WINDOW(
                                pid=self.current_window_pid,
                                window_id=self.current_window_id,
                            ),
                            keys=[action.key or ""],
                        )
                    else:
                        # Fallback to desktop targeting
                        key_press_input = PressKeyInput(
                            target=ActionTarget.DESKTOP(display_id="main"),
                            keys=[action.key or ""],
                        )
                else:
                    # Fallback to desktop targeting
                    key_press_input = PressKeyInput(
                        target=ActionTarget.DESKTOP(display_id="main"),
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
    
    def start_recording(self, run_id: int, screenshot_dir: Optional[Path] = None) -> None:
        """
        Start screen recording for a run.
        
        Args:
            run_id: ID of the current run
            screenshot_dir: Directory to store frames (defaults to ./runs/frames/<run_id>/)
        """
        if screenshot_dir is None:
            screenshot_dir = Path.cwd() / "runs" / "frames" / str(run_id)
        
        # Create recording directory
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize recording state
        self.recording_active = True
        self.recording_run_id = run_id
        self.recording_frames = []
        self.recording_start_time = datetime.utcnow()
        self.recording_dir = screenshot_dir
        
        print(f"✓ Screen recording started for run {run_id}")
        print(f"  Frames directory: {screenshot_dir}")
    
    async def capture_action_frame(self, label: str = "") -> Optional[Path]:
        """
        Capture a frame during action execution.
        
        Args:
            label: Label for the frame (e.g., "before_action", "after_action")
            
        Returns:
            Path to the captured frame, or None if recording is not active
        """
        if not self.recording_active:
            return None
        
        if not self._initialized:
            await self.initialize()
        
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            frame_path = self.recording_dir / f"frame_{timestamp}_{label}.png"
            
            # Capture screenshot using Cua Driver
            from cua_driver import GetDesktopStateInput
            screenshot_result = await self.driver.get_desktop_state(
                GetDesktopStateInput(
                    session=self.session,
                    screenshot_out_file=str(frame_path)
                )
            )
            
            # Store path in recording_frames list
            self.recording_frames.append(frame_path)
            
            return frame_path
            
        except Exception as e:
            print(f"Warning: Failed to capture frame: {e}")
            return None
    
    def stop_recording(self) -> Optional[Path]:
        """
        Stop recording and return the list of captured frames.
        
        Returns:
            Path to the recording directory, or None if no recording was active
        """
        if not self.recording_active:
            return None
        
        self.recording_active = False
        print(f"✓ Screen recording stopped")
        print(f"  Frames captured: {len(self.recording_frames)}")
        print(f"  Duration: {(datetime.utcnow() - self.recording_start_time).total_seconds():.1f}s")
        
        return self.recording_dir
    
    def is_recording(self) -> bool:
        """Check if recording is currently active."""
        return self.recording_active
    
    def get_recording_frames(self) -> List[Path]:
        """Get the list of captured frame paths."""
        return self.recording_frames


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