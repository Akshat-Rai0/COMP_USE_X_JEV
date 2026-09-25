Screen Recording and GIF Feature Implementation
Implement hybrid screen recording (capture during actions only) with automatic GIF conversion, always enabled by default, with retention limit for old recordings.

Screen Recording and GIF Feature Implementation Plan
Overview
Add a feature to automatically record the screen during agent execution and convert the recording to a GIF file for visual documentation and debugging purposes.

User Configuration:

Recording Approach: Hybrid (capture only during actual actions, skip idle time)
Recording Trigger: Always enabled for all tasks
Storage Management: Keep only the most recent N recordings (configurable)
Current State Analysis
Existing Screenshot Infrastructure
Cua Driver already captures individual screenshots to runs directory
Screenshots are stored as PNG files with timestamps
TraceWriter records screenshot paths in SQLite database
Current: Single screenshots per step, not continuous recording
Key Files to Modify
driver.py - Add screen recording methods
loop.py - Integrate recording start/stop into execution loop
writer.py - Add GIF file path to run metadata
pyproject.toml - Add screen recording and GIF conversion dependencies
reflex.py - Add recording configuration options
.env.example - Add recording configuration variables
Implementation Approach
Phase 1: Dependencies and Recording Infrastructure
1.1 Add Required Dependencies
GIF conversion: imageio>=2.30.0 for GIF creation from screenshots
Configuration: Add recording options to LoopConfig
File: pyproject.toml

dependencies = [
    # ... existing dependencies ...
    "imageio>=2.30.0",     # For GIF creation
    "imageio-ffmpeg>=0.4.7",  # For video processing if needed
]
1.2 Add Recording Configuration
File: loop.py - Extend LoopConfig

@dataclass
class LoopConfig:
    # ... existing fields ...
    record_screen: bool = True  # Always enabled by default
    create_gif: bool = True   # Convert recording to GIF
    max_recordings: int = 10  # Keep only most recent N recordings
    capture_idle: bool = False  # Hybrid: skip idle time
File: .env.example

# Screen Recording Configuration
RECORD_SCREEN=true
CREATE_GIF=true
MAX_RECORDINGS=10
CAPTURE_IDLE=false
Phase 2: Hybrid Recording Implementation
2.1 Add Recording Methods to CuaBody
File: driver.py - Add to CuaBody class

Methods to add:

start_recording(run_id: int) - Initialize recording for a run
capture_action_frame() - Capture screenshot during action execution
stop_recording() - Stop recording and compile GIF
is_recording() - Check if recording is active
State variables:

recording_active: bool
recording_run_id: Optional[int]
recording_frames: List[Path] - Store paths to captured frames
recording_start_time: Optional[datetime]
Hybrid approach implementation:

Capture screenshot before each action execution
Skip idle time between actions
Capture screenshot after action completion for verification
Store frames in temporary directory during execution
2.2 Add Recording Lifecycle Management
File: driver.py - Add state management

Frame capture logic:

async def capture_action_frame(self, label: str = "") -> Path:
    """Capture a frame during action execution."""
    if not self.recording_active:
        return None
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    frame_path = self.screenshot_dir / f"frame_{self.recording_run_id}_{timestamp}_{label}.png"
    
    # Capture screenshot using Cua Driver
    # Store path in recording_frames list
    self.recording_frames.append(frame_path)
    
    return frame_path
Phase 3: Orchestrator Integration
3.1 Integrate Recording into Execution Loop
File: loop.py - Modify run_task function

Integration points:

Start recording before task execution begins
Capture frame before each action
Capture frame after each action
Stop recording after task completion/failure
Handle recording errors gracefully
Continue execution even if recording fails
Changes to run_task:

async def run_task(task: str, body: Body, config: LoopConfig):
    # Start recording if enabled
    if config.record_screen and isinstance(body, CuaBody):
        run_id = trace_writer.start_run(...)
        body.start_recording(run_id)
    
    try:
        while not done:
            # Capture frame before action
            if config.record_screen and isinstance(body, CuaBody):
                body.capture_action_frame("before_action")
            
            # Execute action
            # ... existing action execution ...
            
            # Capture frame after action
            if config.record_screen and isinstance(body, CuaBody):
                body.capture_action_frame("after_action")
    
    finally:
        # Stop recording and convert to GIF
        if config.record_screen and isinstance(body, CuaBody):
            gif_path = body.stop_recording()
            if config.create_gif and gif_path:
                trace_writer.update_run_gif(run_id, gif_path)
            trace_writer.cleanup_old_recordings(config.max_recordings)
Phase 4: GIF Conversion
4.1 Implement GIF Conversion Function
File: gif_converter.py - New utility module

Function signature:

def convert_frames_to_gif(
    frame_paths: List[Path],
    output_path: Path,
    duration: float = 0.5,  # Duration per frame
    loop: bool = True,
    optimize: bool = True
) -> Path
Implementation:

Use imageio to read PNG frames
Create GIF with specified duration per frame
Optimize for file size if enabled
Handle errors gracefully
Cleanup temporary frames after GIF creation
4.2 Add GIF Conversion to TraceWriter
File: writer.py - Extend database schema

Schema addition:

ALTER TABLE runs ADD COLUMN gif_path TEXT
Method addition:

def update_run_gif(self, run_id: int, gif_path: Path) -> None:
    """Update run with GIF path."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE runs SET gif_path = ? WHERE id = ?
        """, (str(gif_path), run_id))
        conn.commit()
 
def cleanup_old_recordings(self, max_keep: int = 10) -> int:
    """Delete old GIFs and frames, keeping only the most recent N."""
    # Get list of runs sorted by start_time
    # Identify runs to delete
    # Delete GIF files and frame directories
    # Update database to remove gif_path
Phase 5: Recording Retention Management
5.1 Implement Retention Policy
File: writer.py - Add cleanup method

Logic:

def cleanup_old_recordings(self, max_keep: int = 10) -> int:
    """Keep only the most recent N recordings."""
    # Get all runs with gif_path
    # Sort by start_time DESC
    # Keep top N, delete the rest
    # Delete GIF files
    # Delete frame directories
    # Update database to set gif_path to NULL
    # Return count of deleted recordings
Phase 6: CLI Integration
6.1 Add Recording CLI Options
File: reflex.py - Add command-line options

New commands:

python reflex.py run "task" --no-record  # Disable recording
python reflex.py run "task" --no-gif     # Disable GIF conversion
python reflex.py run "task" --keep 20    # Keep 20 recordings
Changes:

Add --no-record flag to disable recording
Add --no-gif flag to skip GIF conversion
Add --keep parameter for retention limit
Override .env settings with CLI flags
Phase 7: Testing and Validation
7.1 Add Recording Tests
File: tests/test_recording.py - New test file

Test cases:

Test recording start/stop functionality
Test frame capture during actions
Test GIF conversion from frames
Test recording during fake task execution
Test error handling when recording fails
Test retention policy cleanup
7.2 Integration Test
File: test_recording_integration.py - New integration test

Test scenario:

Run a simple task with recording enabled
Verify frames are captured during actions
Verify GIF is generated
Verify GIF can be played back
Verify old recordings are cleaned up
Technical Implementation Details
Hybrid Recording Flow
Before Task Execution
Create temporary directory for frames: runs/frames/<run_id>/
Initialize recording state
During Action Execution
Capture frame before action: frame_<run_id>_<timestamp>_before_action.png
Execute action
Capture frame after action: frame_<run_id>_<timestamp>_after_action.png
Store frame paths in list
After Task Completion
Compile all frames into GIF: runs/gifs/run_<run_id>_<timestamp>.gif
Store GIF path in database
Cleanup old recordings based on retention policy
Delete temporary frame directory
File Management
Naming convention:

Frames: runs/frames/<run_id>/frame_<timestamp>_<label>.png
GIF: runs/gifs/run_<run_id>_<timestamp>.gif
Directory structure:

runs/
├── frames/
│   ├── 1/
│   │   ├── frame_001_before_action.png
│   │   ├── frame_001_after_action.png
│   │   └── ...
│   ├── 2/
│   └── ...
├── gifs/
│   ├── run_1_20250925_120000.gif
│   ├── run_2_20250925_121500.gif
│   └── ...
└── traces.sqlite
Performance Impact
Resource usage:

CPU: Minimal (only during action execution)
Disk: ~1-2MB per frame, ~10-20MB per typical task
Memory: Minimal (storing only file paths, not images in memory)
Optimizations:

Skip idle time (hybrid approach)
Capture only during actions
Configurable frame quality
Auto-cleanup of old recordings
Implementation Steps
Step 1: Add Dependencies
Add imageio>=2.30.0 and imageio-ffmpeg>=0.4.7 to pyproject.toml
Install dependencies in virtual environment
Step 2: Create Recording Utility Module
Create gif_converter.py
Implement frame-to-GIF conversion
Test with existing screenshots
Step 3: Extend CuaBody with Recording
Add recording state variables
Implement start_recording() method
Implement capture_action_frame() method
Implement stop_recording() method
Create temporary frame directory management
Step 4: Integrate into Orchestrator
Modify run_task() to start/stop recording
Add frame capture before/after actions
Add error handling for recording failures
Ensure recording doesn't block main execution
Step 5: Extend TraceWriter
Add gif_path column to runs table
Implement update_run_gif() method
Implement cleanup_old_recordings() method
Add schema migration for existing databases
Step 6: Update CLI
Add --no-record flag to run command
Add --no-gif flag
Add --keep parameter
Update help text
Step 7: Update Configuration
Add recording variables to .env.example
Update LoopConfig with recording options
Set recording enabled by default
Step 8: Testing
Create unit tests for recording functionality
Create integration test with full workflow
Test with real app execution
Verify GIF playback
Test retention policy
Step 9: Documentation
Update README.md with recording feature
Update PROJECT_STATE.md with new achievement
Add usage examples
Risks and Mitigations
Risk 1: Recording Permission Issues
Risk: macOS may require additional permissions for screen recording
Mitigation: Hybrid approach uses existing screenshot infrastructure, no additional permissions needed
Risk 2: Performance Impact
Risk: Recording may slow down agent execution
Mitigation: Hybrid approach only captures during actions, minimal overhead
Risk 3: File Size Management
Risk: Recordings may consume significant disk space
Mitigation: Retention policy keeps only most recent N recordings
Risk 4: GIF Conversion Failures
Risk: GIF conversion may fail with corrupted frames
Mitigation: Graceful error handling, keep original frames for debugging
Risk 5: Frame Loss During Execution
Risk: Frames may not be captured if action fails abruptly
Mitigation: Try-finally blocks ensure cleanup, partial GIFs are still useful
Success Criteria
 Recording enabled by default for all tasks
 Frames captured before and after each action
 GIF generated from captured frames
 GIF playback shows agent actions
 Recording failures don't prevent task execution
 Retention policy keeps only N most recent recordings
 Old recordings automatically cleaned up
 Tests pass for recording functionality
 Documentation updated
 CLI flags allow disabling recording if needed