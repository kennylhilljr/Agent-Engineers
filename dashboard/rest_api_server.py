"""
REST API server for dashboard with acceleration endpoints.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="Dashboard API")


class AccelerationController:
    """Controller for acceleration endpoints."""
    
    def __init__(self):
        self.acceleration_enabled = False
        self.acceleration_factor = 1.5
        self.active_acceleration_tasks = {}
    
    async def enable_acceleration(self, factor: float = 1.5) -> Dict[str, Any]:
        """Enable acceleration with specified factor."""
        if factor < 1.0 or factor > 10.0:
            raise ValueError("Acceleration factor must be between 1.0 and 10.0")
        
        self.acceleration_enabled = True
        self.acceleration_factor = factor
        
        logger.info(f"Acceleration enabled with factor {factor}")
        
        return {
            'status': 'enabled',
            'acceleration_factor': factor,
            'timestamp': self._get_timestamp()
        }
    
    async def disable_acceleration(self) -> Dict[str, Any]:
        """Disable acceleration."""
        self.acceleration_enabled = False
        
        logger.info("Acceleration disabled")
        
        return {
            'status': 'disabled',
            'timestamp': self._get_timestamp()
        }
    
    async def get_acceleration_status(self) -> Dict[str, Any]:
        """Get current acceleration status."""
        return {
            'enabled': self.acceleration_enabled,
            'acceleration_factor': self.acceleration_factor,
            'active_tasks': len(self.active_acceleration_tasks),
            'timestamp': self._get_timestamp()
        }
    
    async def submit_accelerated_task(
        self,
        task_id: str,
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit a task for accelerated execution."""
        if not self.acceleration_enabled:
            raise RuntimeError("Acceleration is not enabled")
        
        self.active_acceleration_tasks[task_id] = {
            'status': 'running',
            'submitted_at': self._get_timestamp(),
            'data': task_data
        }
        
        logger.info(f"Accelerated task {task_id} submitted")
        
        return {
            'task_id': task_id,
            'status': 'submitted',
            'acceleration_factor': self.acceleration_factor,
            'timestamp': self._get_timestamp()
        }
    
    async def get_accelerated_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of an accelerated task."""
        if task_id not in self.active_acceleration_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task = self.active_acceleration_tasks[task_id]
        
        return {
            'task_id': task_id,
            'status': task['status'],
            'submitted_at': task['submitted_at'],
            'timestamp': self._get_timestamp()
        }
    
    async def get_acceleration_metrics(self) -> Dict[str, Any]:
        """Get comprehensive acceleration metrics."""
        completed_tasks = sum(
            1 for t in self.active_acceleration_tasks.values()
            if t['status'] == 'completed'
        )
        
        return {
            'acceleration_enabled': self.acceleration_enabled,
            'acceleration_factor': self.acceleration_factor,
            'total_active_tasks': len(self.active_acceleration_tasks),
            'completed_tasks': completed_tasks,
            'pending_tasks': len(self.active_acceleration_tasks) - completed_tasks,
            'timestamp': self._get_timestamp()
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO format string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'


# Global acceleration controller
acceleration_controller = AccelerationController()


@app.post("/api/acceleration/enable")
async def enable_acceleration_endpoint(factor: float = 1.5) -> Dict[str, Any]:
    """Enable acceleration endpoint."""
    try:
        return await acceleration_controller.enable_acceleration(factor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/acceleration/disable")
async def disable_acceleration_endpoint() -> Dict[str, Any]:
    """Disable acceleration endpoint."""
    return await acceleration_controller.disable_acceleration()


@app.get("/api/acceleration/status")
async def get_acceleration_status_endpoint() -> Dict[str, Any]:
    """Get acceleration status endpoint."""
    return await acceleration_controller.get_acceleration_status()


@app.post("/api/acceleration/submit")
async def submit_accelerated_task_endpoint(
    task_id: str,
    task_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Submit an accelerated task endpoint."""
    try:
        return await acceleration_controller.submit_accelerated_task(task_id, task_data)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/acceleration/task/{task_id}")
async def get_accelerated_task_status_endpoint(task_id: str) -> Dict[str, Any]:
    """Get accelerated task status endpoint."""
    return await acceleration_controller.get_accelerated_task_status(task_id)


@app.get("/api/acceleration/metrics")
async def get_acceleration_metrics_endpoint() -> Dict[str, Any]:
    """Get acceleration metrics endpoint."""
    return await acceleration_controller.get_acceleration_metrics()


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
