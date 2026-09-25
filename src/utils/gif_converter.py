"""
GIF Converter - Convert screenshots to animated GIFs.

This module handles:
- Converting a sequence of PNG screenshots to an animated GIF
- Optimizing GIF file size
- Error handling for corrupted frames
"""

import imageio
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def convert_frames_to_gif(
    frame_paths: List[Path],
    output_path: Path,
    duration: float = 0.5,
    loop: bool = True,
    optimize: bool = True,
    fps: int = 2
) -> Optional[Path]:
    """
    Convert a sequence of PNG frames to an animated GIF.
    
    Args:
        frame_paths: List of paths to PNG frame files
        output_path: Path where the GIF should be saved
        duration: Duration per frame in seconds (if fps not specified)
        loop: Whether the GIF should loop (True = infinite loop)
        optimize: Whether to optimize the GIF for file size
        fps: Frames per second for the GIF
        
    Returns:
        Path to the created GIF, or None if conversion failed
    """
    if not frame_paths:
        logger.warning("No frames provided for GIF conversion")
        return None
    
    if len(frame_paths) == 1:
        logger.warning("Only one frame provided, GIF not created")
        return None
    
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read frames
        frames = []
        for frame_path in frame_paths:
            if not frame_path.exists():
                logger.warning(f"Frame not found: {frame_path}")
                continue
            try:
                frame = imageio.imread(frame_path)
                frames.append(frame)
            except Exception as e:
                logger.warning(f"Failed to read frame {frame_path}: {e}")
        
        if not frames:
            logger.error("No valid frames to convert")
            return None
        
        # Calculate duration per frame based on fps
        if fps:
            duration = 1.0 / fps
        
        # Save as GIF
        imageio.mimsave(
            output_path,
            frames,
            duration=duration,
            loop=0 if loop else 1,
            fps=fps if fps else None,
        )
        
        logger.info(f"GIF created successfully: {output_path}")
        logger.info(f"  Frames: {len(frames)}")
        logger.info(f"  Duration per frame: {duration}s")
        logger.info(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to create GIF: {e}")
        return None


def cleanup_frames(frame_paths: List[Path]) -> int:
    """
    Delete frame files after GIF creation.
    
    Args:
        frame_paths: List of paths to frame files to delete
        
    Returns:
        Number of files deleted
    """
    deleted_count = 0
    for frame_path in frame_paths:
        try:
            if frame_path.exists():
                frame_path.unlink()
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete frame {frame_path}: {e}")
    
    logger.info(f"Deleted {deleted_count} frame files")
    return deleted_count