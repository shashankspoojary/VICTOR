# app/services/code_analysis_service.py
import ast
from pathlib import Path
from typing import Dict, Any, List

class CodeAnalysisService:
    """Performs abstract syntax analysis and metrics evaluation on functional source files."""

    def analyze_source_file(self, path: Path) -> Dict[str, Any]:
        """Parses concrete source scripts to discover structural classes, dependencies, and syntax issues."""
        if not path.exists() or not path.is_file():
            return {"success": False, "error": "Target file path resolved invalid physical tracking state."}
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
                
            tree = ast.parse(source)
            
            analyzer = _ASTStructureExtractor()
            analyzer.visit(tree)
            
            return {
                "success": True,
                "classes": analyzer.discovered_classes,
                "functions": analyzer.discovered_functions,
                "imports": analyzer.discovered_imports,
                "metrics": {
                    "total_chars": len(source),
                    "lines_discovered": len(source.splitlines())
                }
            }
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Static parsing syntax violation: {e.msg}",
                "line_number": e.lineno
            }
        except Exception as e:
            return {"success": False, "error": f"Analysis execution failure context: {str(e)}"}

class _ASTStructureExtractor(ast.NodeVisitor):
    def __init__(self):
        self.discovered_classes: List[str] = []
        self.discovered_functions: List[str] = []
        self.discovered_imports: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.discovered_classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.discovered_functions.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for name in node.names:
            self.discovered_imports.append(name.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.discovered_imports.append(node.module)
        self.generic_visit(node)