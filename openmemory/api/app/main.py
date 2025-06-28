from fastapi.responses import FileResponse
import os

@app.get("/download/claude-extension")
async def download_claude_extension():
    """Serve the Jean Memory Claude Desktop Extension file"""
    file_path = os.path.join(os.path.dirname(__file__), "static", "jean-memory.dxt")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Extension file not found")
    
    return FileResponse(
        path=file_path,
        filename="jean-memory.dxt",
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=jean-memory.dxt",
            "Content-Description": "Jean Memory Claude Desktop Extension"
        }
    ) 