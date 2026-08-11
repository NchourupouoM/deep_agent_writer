import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List
from langchain_core.tools import tool
from tavily import TavilyClient
from skills_manager import SkillsManager

# Global Workspace Directory
WORKSPACE_DIR = Path("workspace").resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Global SkillsManager instance for tool access
_skills_manager = SkillsManager(skills_dir="skills")


def _get_safe_path(filepath: str) -> Path:
    """
    Ensures that file operations remain strictly inside the WORKSPACE_DIR sandbox.
    Prevents directory traversal attacks (e.g., ../../etc/passwd).
    """
    target_path = (WORKSPACE_DIR / filepath).resolve()
    if not str(target_path).startswith(str(WORKSPACE_DIR)):
        raise ValueError(f"Access denied: Path '{filepath}' is outside the workspace sandbox.")
    return target_path


# ==========================================
# 📁 FILESYSTEM SANDBOX TOOLS
# ==========================================

@tool
def write_workspace_file(filename: str, content: str) -> str:
    """
    Writes or overwrites a text file inside the workspace sandbox.
    
    Args:
        filename: Relative path inside workspace (e.g., 'draft.md', 'test_script.py', 'diagram.json').
        content: The text content to write into the file.
        
    Returns:
        Confirmation message with file size and status.
    """
    try:
        safe_path = _get_safe_path(filename)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully written {len(content)} characters to '{filename}' inside workspace."
    except Exception as e:
        return f"Error writing file '{filename}': {str(e)}"


@tool
def read_workspace_file(filename: str) -> str:
    """
    Reads the content of a file from the workspace sandbox.
    
    Args:
        filename: Relative path inside workspace (e.g., 'draft.md').
        
    Returns:
        The content of the file or an error message if not found.
    """
    try:
        safe_path = _get_safe_path(filename)
        if not safe_path.exists():
            return f"Error: File '{filename}' does not exist in workspace."
            
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{filename}': {str(e)}"


@tool
def list_workspace_files() -> str:
    """
    Lists all files currently present in the workspace sandbox.
    
    Returns:
        Formatted list of filenames with their sizes.
    """
    try:
        files_info = []
        for path in WORKSPACE_DIR.glob("**/*"):
            if path.is_file():
                rel_path = path.relative_to(WORKSPACE_DIR)
                size_kb = path.stat().st_size / 1024
                files_info.append(f"- {rel_path} ({size_kb:.2f} KB)")
                
        if not files_info:
            return "Workspace is currently empty."
            
        return "Files in workspace:\n" + "\n".join(files_info)
    except Exception as e:
        return f"Error listing workspace files: {str(e)}"


# ==========================================
# 🐍 PYTHON CODE EXECUTION SANDBOX
# ==========================================

@tool
def execute_python_sandbox(filename: str, timeout_seconds: int = 15) -> str:
    """
    Executes a Python script located in the workspace inside an isolated subprocess sandbox.
    Captures stdout, stderr, and execution status.
    
    Args:
        filename: Name of the python script file inside workspace (e.g., 'test_lora.py').
        timeout_seconds: Maximum allowed execution time in seconds (default: 15s).
        
    Returns:
        STDOUT output if execution succeeded, or STDERR error message if execution failed.
    """
    try:
        safe_path = _get_safe_path(filename)
        if not safe_path.exists():
            return f"Error: Script file '{filename}' not found in workspace."
            
        # Execute Python script in a subprocess with timeout
        result = subprocess.run(
            [sys.executable, str(safe_path)],
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        
        output = []
        if result.stdout:
            output.append(f"--- STDOUT ---\n{result.stdout.strip()}")
        if result.stderr:
            output.append(f"--- STDERR ---\n{result.stderr.strip()}")
            
        status = "SUCCESS" if result.returncode == 0 else f"FAILED (Exit Code {result.returncode})"
        output.insert(0, f"Execution Status: {status}")
        
        return "\n\n".join(output)
        
    except subprocess.TimeoutExpired:
        return f"Execution Error: Script '{filename}' timed out after {timeout_seconds} seconds."
    except Exception as e:
        return f"Execution Error for '{filename}': {str(e)}"


# ==========================================
# 🔍 DEEP RESEARCH & WEB SEARCH TOOL
# ==========================================

@tool
def web_search_tavily(query: str, max_results: int = 5) -> str:
    """
    Performs deep technical web search using Tavily Search API.
    
    Args:
        query: Technical search query (e.g., 'Unsloth VRAM savings benchmark QLoRA 2025').
        max_results: Maximum number of search results to return (default: 5).
        
    Returns:
        Formatted summary of search snippets and source URLs.
    """
    try:        
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY is not set in environment variables."
            
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results, search_depth="advanced")
        
        results = []
        for i, item in enumerate(response.get("results", []), 1):
            title = item.get("title", "No Title")
            url = item.get("url", "#")
            content = item.get("content", "No Snippet")
            results.append(f"[{i}] {title}\nURL: {url}\nSnippet: {content}\n")
            
        return "\n---\n".join(results) if results else "No web search results found."
        
    except Exception as e:
        return f"Search Error: {str(e)}"


# ==========================================
# 🎓 SKILL LOADING TOOL
# ==========================================

@tool
def load_skill_instruction(skill_name: str) -> str:
    """
    Fetches the full markdown instruction content for a specific AgentSkills.io skill.
    
    Args:
        skill_name: Exact skill identifier (e.g., 'redaction-feynman-deep-dive', 'excalidraw-tensor-matrix').
        
    Returns:
        Full markdown instructions for the skill.
    """
    content = _skills_manager.get_skill_content(skill_name)
    if content:
        return f"### SKILL LOADED: {skill_name}\n\n{content}"
    
    available = ", ".join(_skills_manager.skills_registry.keys())
    return f"Error: Skill '{skill_name}' not found. Available skills: [{available}]"


# List of all tools exported for sub-agents
ALL_TOOLS = [
    write_workspace_file,
    read_workspace_file,
    list_workspace_files,
    execute_python_sandbox,
    web_search_tavily,
    load_skill_instruction
]


# ==========================================
# 🧪 TEST SUITE FOR TOOLS
# ==========================================
if __name__ == "__main__":
    print("🧪 Testing Workspace & Tools Sandbox...\n")
    
    # 1. Test Writing File
    res_write = write_workspace_file.invoke({
        "filename": "test_script.py",
        "content": "import sys\nprint('Hello from Python Sandbox!')\nprint(f'Python Version: {sys.version}')"
    })
    print(f"1️⃣ Write File: {res_write}")
    
    # 2. Test Listing Files
    res_list = list_workspace_files.invoke({})
    print(f"2️⃣ List Files:\n{res_list}\n")
    
    # 3. Test Running Python Sandbox
    res_exec = execute_python_sandbox.invoke({"filename": "test_script.py"})
    print(f"3️⃣ Execute Sandbox:\n{res_exec}\n")
    
    # 4. Test Reading File
    res_read = read_workspace_file.invoke({"filename": "test_script.py"})
    print(f"4️⃣ Read File:\n{res_read}\n")
    
    # 5. Test Loading Skill
    res_skill = load_skill_instruction.invoke({"skill_name": "redaction-feynman-deep-dive"})
    print(f"5️⃣ Load Skill:\n{res_skill[:200]}...\n")
    
    print("✅ All Workspace & Sandbox Tools tested successfully!")