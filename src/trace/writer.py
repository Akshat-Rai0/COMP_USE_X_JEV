"""
Trace Writer - SQLite database logging for execution traces.

This module handles:
- Creating and managing SQLite database for trace storage
- Writing step records with full execution details
- Storing screenshot references
- Querying trace data for analysis and replay
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from src.models import StepRecord, OrchestratorState


class TraceWriter:
    """Writer for execution traces to SQLite database."""
    
    def __init__(self, db_path: Optional[Path] = None, screenshot_dir: Optional[Path] = None):
        """
        Initialize the trace writer.
        
        Args:
            db_path: Path to SQLite database file (defaults to ./runs/traces.sqlite)
            screenshot_dir: Directory for screenshot storage (defaults to ./runs)
        """
        if db_path is None:
            db_path = Path.cwd() / "runs" / "traces.sqlite"
        
        if screenshot_dir is None:
            screenshot_dir = Path.cwd() / "runs"
        
        self.db_path = db_path
        self.screenshot_dir = screenshot_dir
        
        # Create directories if they don't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Main runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    total_steps INTEGER DEFAULT 0,
                    successful BOOLEAN,
                    error_message TEXT,
                    total_cost REAL DEFAULT 0.0,
                    backend_model TEXT,
                    planner_model TEXT,
                    metadata JSON,
                    gif_path TEXT
                )
            """)
            
            # Steps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    step_number INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    window_title TEXT,
                    app_name TEXT,
                    element_count INTEGER,
                    screenshot_path TEXT,
                    model_version TEXT,
                    chosen_element TEXT,
                    action_type TEXT,
                    confidence REAL,
                    escalated BOOLEAN,
                    escalation_reason TEXT,
                    human_approval_required BOOLEAN,
                    human_approval_granted BOOLEAN,
                    error TEXT,
                    latency_ms REAL,
                    decision_request JSON,
                    decision_response JSON,
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                )
            """)
            
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_steps_run_id 
                ON steps (run_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_steps_timestamp 
                ON steps (timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_start_time 
                ON runs (start_time)
            """)
            
            # Add gif_path column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE runs ADD COLUMN gif_path TEXT")
            except sqlite3.OperationalError:
                # Column already exists, ignore error
                pass
            
            conn.commit()
    
    def start_run(
        self,
        task: str,
        backend_model: str,
        planner_model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Start a new run and return its ID.
        
        Args:
            task: Task description
            backend_model: Decision backend model version
            planner_model: Planner model version
            metadata: Additional metadata as JSON
            
        Returns:
            Run ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO runs (
                    task, start_time, backend_model, planner_model, metadata
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                task,
                datetime.utcnow().isoformat(),
                backend_model,
                planner_model,
                json.dumps(metadata) if metadata else None,
            ))
            
            run_id = cursor.lastrowid
            conn.commit()
            
            return run_id
    
    def write_step(self, run_id: int, step_record: StepRecord) -> None:
        """
        Write a step record to the database.
        
        Args:
            run_id: Run ID to associate this step with
            step_record: Step record to write
        """
        step_dict = step_record.to_dict()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO steps (
                    run_id, step_number, timestamp, window_title, app_name,
                    element_count, screenshot_path, model_version, chosen_element,
                    action_type, confidence, escalated, escalation_reason,
                    human_approval_required, human_approval_granted, error,
                    latency_ms, decision_request, decision_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                step_dict["step_number"],
                step_dict["timestamp"],
                step_dict["window_title"],
                step_dict["app_name"],
                step_dict["element_count"],
                step_dict["screenshot_path"],
                step_dict["model_version"],
                step_dict["chosen_element"],
                step_dict["action_type"],
                step_dict["confidence"],
                step_dict["escalated"],
                step_dict["escalation_reason"],
                step_dict["human_approval_required"],
                step_dict["human_approval_granted"],
                step_dict["error"],
                step_dict["latency_ms"],
                json.dumps(asdict(step_record.decision_request), default=str),
                json.dumps(asdict(step_record.decision_response), default=str),
            ))
            
            # Update run step count
            cursor.execute("""
                UPDATE runs SET total_steps = total_steps + 1 WHERE id = ?
            """, (run_id,))
            
            conn.commit()
    
    def end_run(
        self,
        run_id: int,
        successful: bool,
        error_message: Optional[str] = None,
        total_cost: float = 0.0,
    ) -> None:
        """
        Mark a run as completed.
        
        Args:
            run_id: Run ID to complete
            successful: Whether the run was successful
            error_message: Error message if unsuccessful
            total_cost: Total cost of the run
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE runs 
                SET end_time = ?, successful = ?, error_message = ?, total_cost = ?
                WHERE id = ?
            """, (
                datetime.utcnow().isoformat(),
                successful,
                error_message,
                total_cost,
                run_id,
            ))
            
            conn.commit()
    
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a run by ID.
        
        Args:
            run_id: Run ID
            
        Returns:
            Run data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM runs WHERE id = ?
            """, (run_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_steps(self, run_id: int) -> List[Dict[str, Any]]:
        """
        Get all steps for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of step data
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM steps WHERE run_id = ? ORDER BY step_number
            """, (run_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent runs.
        
        Args:
            limit: Maximum number of runs to return
            
        Returns:
            List of run data
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM runs 
                ORDER BY start_time DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_success_rate(self, task: Optional[str] = None) -> float:
        """
        Calculate success rate for runs.
        
        Args:
            task: Optional task filter
            
        Returns:
            Success rate (0.0 to 1.0)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if task:
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN successful = 1 THEN 1 END) * 1.0 / COUNT(*) as success_rate
                    FROM runs 
                    WHERE task = ?
                """, (task,))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN successful = 1 THEN 1 END) * 1.0 / COUNT(*) as success_rate
                    FROM runs
                """)
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                return result[0]
            return 0.0
    
    def get_average_latency(self, run_id: Optional[int] = None) -> float:
        """
        Calculate average decision latency.
        
        Args:
            run_id: Optional run ID filter
            
        Returns:
            Average latency in milliseconds
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if run_id:
                cursor.execute("""
                    SELECT AVG(latency_ms) FROM steps WHERE run_id = ?
                """, (run_id,))
            else:
                cursor.execute("""
                    SELECT AVG(latency_ms) FROM steps
                """)
            
            result = cursor.fetchone()
            if result and result[0] is not None:
                return result[0]
            return 0.0
    
    def cleanup_old_runs(self, days: int = 30) -> int:
        """
        Delete runs older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of runs deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM runs 
                WHERE start_time < datetime('now', '-' || ? || ' days')
            """, (days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
    
    def export_run_json(self, run_id: int, output_path: Path) -> None:
        """
        Export a run to JSON file.
        
        Args:
            run_id: Run ID to export
            output_path: Path to write JSON file
        """
        run_data = self.get_run(run_id)
        if not run_data:
            raise ValueError(f"Run {run_id} not found")
        
        steps = self.get_steps(run_id)
        
        export_data = {
            "run": run_data,
            "steps": steps,
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
    
    def update_run_gif(self, run_id: int, gif_path: Path) -> None:
        """
        Update a run with GIF path.
        
        Args:
            run_id: Run ID to update
            gif_path: Path to the GIF file
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE runs SET gif_path = ? WHERE id = ?
            """, (str(gif_path), run_id))
            conn.commit()
    
    def cleanup_old_recordings(self, max_keep: int = 10) -> int:
        """
        Delete old GIFs and frames, keeping only the most recent N.
        
        Args:
            max_keep: Number of recordings to keep
            
        Returns:
            Number of recordings deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all runs with gif_path, sorted by start_time DESC
            cursor.execute("""
                SELECT id, gif_path FROM runs 
                WHERE gif_path IS NOT NULL 
                ORDER BY start_time DESC
            """)
            
            runs = cursor.fetchall()
            
            if len(runs) <= max_keep:
                return 0
            
            # Delete recordings beyond max_keep
            to_delete = runs[max_keep:]
            deleted_count = 0
            
            for run_id, gif_path in to_delete:
                try:
                    # Delete GIF file
                    if gif_path:
                        gif_file = Path(gif_path)
                        if gif_file.exists():
                            gif_file.unlink()
                    
                    # Delete frame directory
                    frame_dir = self.screenshot_dir / "frames" / str(run_id)
                    if frame_dir.exists():
                        import shutil
                        shutil.rmtree(frame_dir)
                    
                    # Update database to remove gif_path
                    cursor.execute("""
                        UPDATE runs SET gif_path = NULL WHERE id = ?
                    """, (run_id,))
                    
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"Warning: Failed to delete recording for run {run_id}: {e}")
            
            conn.commit()
            
            if deleted_count > 0:
                print(f"✓ Cleaned up {deleted_count} old recordings")
            
            return deleted_count