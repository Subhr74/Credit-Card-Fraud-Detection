"""Live Stream, Server-Sent Events (SSE), and Alert Feed Router."""
import json
import asyncio
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from backend.simulator import simulator

router = APIRouter(prefix="/api", tags=["Live Stream & Simulator"])

@router.get("/stream")
async def event_stream(request: Request):
    """Server-Sent Events endpoint streaming real-time scored transactions."""
    queue = simulator.subscribe()

    async def event_generator():
        try:
            while True:
                # Disconnect check
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield ": ping\n\n"
        finally:
            simulator.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/alerts")
def get_alerts():
    """Return the current buffer of high-risk flagged transaction alerts."""
    return {
        "alerts": simulator.alerts_feed,
        "total_alerts": simulator.total_alerts,
        "active_stream": simulator.is_running
    }

@router.post("/simulator/start")
def start_simulator(interval: float = Query(1.5, ge=0.2, le=10.0)):
    """Start the background transaction stream generator."""
    simulator.start(interval=interval)
    return {"status": "RUNNING", "interval": simulator.interval_seconds}

@router.post("/simulator/stop")
def stop_simulator():
    """Stop the background transaction stream generator."""
    simulator.stop()
    return {"status": "STOPPED"}

@router.get("/simulator/status")
def simulator_status():
    """Get live status and telemetry of the transaction stream simulator."""
    return simulator.get_status()
