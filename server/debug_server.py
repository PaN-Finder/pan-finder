#!/usr/bin/env python3
"""
Debug-enabled server startup script for Docker container debugging.
"""

import os

import debugpy


def start_debug_server():
    """Start the debug server and FastAPI application."""
    # Configure debugpy
    debug_port = int(os.getenv("DEBUG_PORT", "5678"))
    debug_wait = os.getenv("DEBUG_WAIT", "false").lower() == "true"

    print(f"Starting debug server on port {debug_port}")
    print(f"Debug wait for client: {debug_wait}")

    # Start debugpy server
    debugpy.listen(("0.0.0.0", debug_port))

    if debug_wait:
        print("Waiting for debugger to attach...")
        debugpy.wait_for_client()
        print("Debugger attached!")

    # Set PYTHONPATH environment variable instead of modifying sys.path
    # This avoids circular import issues
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    src_path = "/code/app/src"

    if src_path not in current_pythonpath:
        if current_pythonpath:
            os.environ["PYTHONPATH"] = f"{src_path}:{current_pythonpath}"
        else:
            os.environ["PYTHONPATH"] = src_path

    # Now we can safely import uvicorn and start the server with the module path
    import uvicorn

    print("Starting FastAPI server...")
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8080")),
        reload=True,
        reload_dirs=["/code/app/src"],
    )


if __name__ == "__main__":
    start_debug_server()
