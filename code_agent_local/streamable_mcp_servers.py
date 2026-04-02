#!/usr/bin/env python3
"""
Streamable HTTP MCP Server Implementation
Provides Python interpreter, file operations and system operations services
Using FastMCP framework for Streamable HTTP protocol
"""

import asyncio
import logging
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List

import uvicorn
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP servers
python_interpreter_mcp = FastMCP(name="PythonInterpreter")
file_operations_mcp = FastMCP(name="FileOperations")


@python_interpreter_mcp.tool()
async def execute_python_code(code: str, timeout: int = 10) -> dict:
    """Execute Python code and return output.
    
    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (default: 10)
    
    Returns:
        Dictionary with status, stdout, stderr, return_code, and execution_time
    """
    logger.info(f"Executing Python code: {code[:100]}...")
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name
    
    try:
        # Execute code
        result = subprocess.run(
            [sys.executable, temp_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd='/tmp'
        )
        
        response_data = {
            'status': 'success' if result.returncode == 0 else 'error',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode,
            'execution_time': datetime.now().isoformat()
        }
        
        return response_data
        
    except subprocess.TimeoutExpired:
        return {
            'status': 'error',
            'error': 'Code execution timeout'
        }
    except Exception as e:
        logger.error(f"Code execution error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
    finally:
        # Clean up temporary file
        os.unlink(temp_file)


@python_interpreter_mcp.tool()
async def check_python_health() -> dict:
    """Check Python interpreter service health.
    
    Returns:
        Dictionary with status and timestamp
    """
    return {
        'status': 'healthy',
        'service': 'python-interpreter',
        'timestamp': datetime.now().isoformat()
    }


# Workspace directory configuration
WORKSPACE_DIR = Path(os.getenv('CODE_AGENT_WORKSPACE_DIR', './working'))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def validate_path(file_path: str) -> bool:
    """Validate if file path is safe.
    
    Args:
        file_path: File path to validate
    
    Returns:
        True if path is within workspace directory, False otherwise
    """
    try:
        file_path = Path(file_path).resolve()
        workspace_path = WORKSPACE_DIR.resolve()
        return str(file_path).startswith(str(workspace_path))
    except:
        return False


@file_operations_mcp.tool()
async def read_file(path: str) -> dict:
    """Read file content.
    
    Args:
        path: File path to read (must be within workspace directory)
    
    Returns:
        Dictionary with status, content, size, and path
    """
    try:
        if not validate_path(path):
            return {
                'status': 'error',
                'error': 'File path is not safe'
            }
        
        file_path = Path(path)
        if not file_path.exists():
            return {
                'status': 'error',
                'error': 'File does not exist'
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'status': 'success',
            'content': content,
            'size': len(content),
            'path': str(file_path)
        }
        
    except Exception as e:
        logger.error(f"Read file error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@file_operations_mcp.tool()
async def write_file(path: str, content: str) -> dict:
    """Write content to file.
    
    Args:
        path: File path to write (must be within workspace directory)
        content: Content to write to file
    
    Returns:
        Dictionary with status, path, and size
    """
    try:
        if not validate_path(path):
            return {
                'status': 'error',
                'error': 'File path is not safe'
            }
        
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            'status': 'success',
            'path': str(file_path),
            'size': len(content)
        }
        
    except Exception as e:
        logger.error(f"Write file error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@file_operations_mcp.tool()
async def list_files(directory: str = None) -> dict:
    """List files in directory.
    
    Args:
        directory: Directory path to list (defaults to workspace directory)
    
    Returns:
        Dictionary with status, files list, and directory
    """
    try:
        if directory is None:
            directory = str(WORKSPACE_DIR)
        
        if not validate_path(directory):
            return {
                'status': 'error',
                'error': 'Directory path is not safe'
            }
        
        directory = Path(directory)
        if not directory.exists():
            return {
                'status': 'error',
                'error': 'Directory does not exist'
            }
        
        files = []
        for item in directory.iterdir():
            file_info = {
                'name': item.name,
                'type': 'directory' if item.is_dir() else 'file',
                'size': item.stat().st_size if item.is_file() else None
            }
            files.append(file_info)
        
        return {
            'status': 'success',
            'files': files,
            'directory': str(directory)
        }
        
    except Exception as e:
        logger.error(f"List files error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


@file_operations_mcp.tool()
async def check_file_health() -> dict:
    """Check file operations service health.
    
    Returns:
        Dictionary with status, workspace, and timestamp
    """
    return {
        'status': 'healthy',
        'service': 'file-operations',
        'workspace': str(WORKSPACE_DIR),
        'timestamp': datetime.now().isoformat()
    }


def create_http_app(mcp_server, path: str = "/mcp") -> any:
    """Create HTTP app with CORS middleware.
    
    Args:
        mcp_server: FastMCP server instance
        path: MCP endpoint path
    
    Returns:
        Starlette application with CORS enabled
    """
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    
    # Create base app
    app = mcp_server.http_app(path=path)
    
    # Add health check endpoint
    async def health_check(request):
        return JSONResponse({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
    
    # Extract service name from path
    service_name = path.strip('/').replace('-', '_')
    app.router.routes.append(Route(f"{path}/health", health_check, methods=["GET"]))
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id"]
    )
    return app


async def start_all_servers():
    """Start all MCP servers"""
    # Create HTTP apps for each server
    python_app = create_http_app(python_interpreter_mcp, path="/python-interpreter")
    file_app = create_http_app(file_operations_mcp, path="/file-operations")
    
    # Start servers on different ports
    python_config = uvicorn.Config(python_app, host="localhost", port=8001, log_level="info")
    file_config = uvicorn.Config(file_app, host="localhost", port=8002, log_level="info")
    
    python_server = uvicorn.Server(python_config)
    file_server = uvicorn.Server(file_config)
    
    logger.info("Starting Python Interpreter MCP server on port 8001")
    logger.info("Starting File Operations MCP server on port 8002")
    
    # Run both servers
    await asyncio.gather(
        python_server.serve(),
        file_server.serve()
    )


if __name__ == "__main__":
    try:
        asyncio.run(start_all_servers())
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
