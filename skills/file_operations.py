"""
File operations skill for AGI agents.
Integrated with Tool Registry for unified tool management.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from .tool_registry import BaseTool, ToolSchema, ToolParameter, ToolCategory, ToolRiskLevel


class FileReadSkill(BaseTool):
    """Tool for reading files with various formats."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_read",
            description="Read content from a file. Supports text, JSON, and partial reading.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Absolute or relative path to the file",
                    required=True
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="Line number to start reading from (0-indexed)",
                    required=False
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of lines to read",
                    required=False
                ),
                ToolParameter(
                    name="as_json",
                    type="boolean",
                    description="Parse content as JSON",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(
        self,
        path: str,
        offset: int = 0,
        limit: int = None,
        as_json: bool = False
    ) -> Dict[str, Any]:
        """Read file with optional offset and limit."""
        path = Path(path).expanduser().resolve()
        
        if not path.exists():
            return {"error": f"File not found: {path}", "exists": False}
        
        if not path.is_file():
            return {"error": f"Path is not a file: {path}", "exists": True}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if as_json:
                    content = json.load(f)
                    return {
                        "path": str(path),
                        "content": content,
                        "format": "json",
                        "exists": True
                    }
                
                lines = f.readlines()
                total_lines = len(lines)
                
                start = offset
                end = offset + limit if limit else total_lines
                selected_lines = lines[start:end]
                
                content = "".join(selected_lines)
                
                return {
                    "path": str(path),
                    "content": content,
                    "total_lines": total_lines,
                    "returned_lines": len(selected_lines),
                    "offset": offset,
                    "exists": True
                }
        
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {str(e)}", "exists": True}
        except Exception as e:
            return {"error": f"Read error: {str(e)}", "exists": True}


class FileWriteSkill(BaseTool):
    """Tool for writing files with safety checks."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_write",
            description="Write content to a file. Creates directories if needed.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to write",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write",
                    required=True
                ),
                ToolParameter(
                    name="append",
                    type="boolean",
                    description="Append to existing file instead of overwriting",
                    required=False
                ),
                ToolParameter(
                    name="backup",
                    type="boolean",
                    description="Create .bak backup before overwriting",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.ELEVATED
        )
    
    def _execute(
        self,
        path: str,
        content: str,
        append: bool = False,
        backup: bool = False
    ) -> Dict[str, Any]:
        """Write file with optional backup."""
        path = Path(path).expanduser().resolve()
        
        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup if needed
        if backup and path.exists() and not append:
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup_path)
        
        try:
            mode = 'a' if append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
            
            return {
                "path": str(path),
                "bytes_written": len(content.encode('utf-8')),
                "appended": append,
                "backup_created": backup and path.exists() and not append
            }
        
        except Exception as e:
            return {"error": f"Write error: {str(e)}"}


class FileListSkill(BaseTool):
    """Tool for listing directory contents."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_list",
            description="List files and directories at a given path",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory path to list",
                    required=True
                ),
                ToolParameter(
                    name="recursive",
                    type="boolean",
                    description="List recursively",
                    required=False
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Glob pattern to filter files (e.g., '*.py')",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(
        self,
        path: str,
        recursive: bool = False,
        pattern: str = None
    ) -> Dict[str, Any]:
        """List directory contents."""
        path = Path(path).expanduser().resolve()
        
        if not path.exists():
            return {"error": f"Path not found: {path}", "exists": False}
        
        if not path.is_dir():
            return {"error": f"Path is not a directory: {path}", "exists": True}
        
        try:
            files = []
            dirs = []
            
            if recursive:
                items = list(path.rglob(pattern or "*"))
            else:
                items = list(path.glob(pattern or "*"))
            
            for item in items:
                stat = item.stat()
                entry = {
                    "name": item.name,
                    "path": str(item),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
                
                if item.is_file():
                    entry["type"] = "file"
                    files.append(entry)
                elif item.is_dir():
                    entry["type"] = "directory"
                    dirs.append(entry)
            
            # Sort by name
            files.sort(key=lambda x: x["name"])
            dirs.sort(key=lambda x: x["name"])
            
            return {
                "path": str(path),
                "exists": True,
                "directories": dirs,
                "files": files,
                "total_count": len(files) + len(dirs)
            }
        
        except Exception as e:
            return {"error": f"List error: {str(e)}"}


class FileSearchSkill(BaseTool):
    """Tool for searching file contents."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_search",
            description="Search for text patterns within files",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory or file path to search",
                    required=True
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Text pattern to search for",
                    required=True
                ),
                ToolParameter(
                    name="file_pattern",
                    type="string",
                    description="Glob pattern for files to include (e.g., '*.py')",
                    required=False
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of matches to return",
                    required=False
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(
        self,
        path: str,
        pattern: str,
        file_pattern: str = "*",
        max_results: int = 50
    ) -> Dict[str, Any]:
        """Search for pattern in files."""
        import re
        
        path = Path(path).expanduser().resolve()
        matches = []
        files_searched = 0
        
        try:
            if path.is_file():
                files = [path]
            else:
                files = list(path.rglob(file_pattern))
                files = [f for f in files if f.is_file()]
            
            for file_path in files:
                files_searched += 1
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.lower() in line.lower():
                                matches.append({
                                    "file": str(file_path),
                                    "line": line_num,
                                    "content": line.strip()[:200]
                                })
                                if len(matches) >= max_results:
                                    break
                        if len(matches) >= max_results:
                            break
                except Exception:
                    continue
            
            return {
                "pattern": pattern,
                "files_searched": files_searched,
                "matches_found": len(matches),
                "matches": matches
            }
        
        except Exception as e:
            return {"error": f"Search error: {str(e)}"}


class FileInfoSkill(BaseTool):
    """Tool for getting file metadata."""
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_info",
            description="Get detailed information about a file or directory",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to get information about",
                    required=True
                )
            ],
            category=ToolCategory.FILE,
            risk_level=ToolRiskLevel.SAFE
        )
    
    def _execute(self, path: str) -> Dict[str, Any]:
        """Get file/directory information."""
        path = Path(path).expanduser().resolve()
        
        if not path.exists():
            return {"exists": False, "path": str(path)}
        
        stat = path.stat()
        
        info = {
            "exists": True,
            "path": str(path),
            "name": path.name,
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "permissions": oct(stat.st_mode)[-3:],
            "absolute": str(path.absolute())
        }
        
        if path.is_file():
            info["extension"] = path.suffix
            info["mime_type"] = self._get_mime_type(path)
        else:
            # Count children
            try:
                children = list(path.iterdir())
                info["children_count"] = len(children)
            except PermissionError:
                info["children_count"] = "permission_denied"
        
        return info
    
    def _get_mime_type(self, path: Path) -> str:
        """Guess MIME type from extension."""
        import mimetypes
        mime, _ = mimetypes.guess_type(str(path))
        return mime or "unknown"


# Convenience functions for direct usage
def read_file(path: str, **kwargs) -> Union[str, Dict, None]:
    """Convenience function to read a file."""
    skill = FileReadSkill()
    result = skill.execute(path=path, **kwargs)
    if result.success:
        return result.data.get("content")
    return None


def write_file(path: str, content: str, **kwargs) -> bool:
    """Convenience function to write a file."""
    skill = FileWriteSkill()
    result = skill.execute(path=path, content=content, **kwargs)
    return result.success


def list_files(path: str, **kwargs) -> List[Dict]:
    """Convenience function to list directory."""
    skill = FileListSkill()
    result = skill.execute(path=path, **kwargs)
    if result.success:
        return result.data.get("files", []) + result.data.get("directories", [])
    return []


def search_files(path: str, pattern: str, **kwargs) -> List[Dict]:
    """Convenience function to search files."""
    skill = FileSearchSkill()
    result = skill.execute(path=path, pattern=pattern, **kwargs)
    if result.success:
        return result.data.get("matches", [])
    return []


if __name__ == "__main__":
    # Demo
    print("=== File Operations Skill Demo ===\n")
    
    # List current directory
    list_skill = FileListSkill()
    result = list_skill.execute(path=".", pattern="*.py")
    print(f"Python files: {json.dumps(result.data, indent=2)[:500]}")
    
    # File info
    info_skill = FileInfoSkill()
    result = info_skill.execute(path=__file__)
    print(f"\nFile info: {json.dumps(result.data, indent=2)}")
