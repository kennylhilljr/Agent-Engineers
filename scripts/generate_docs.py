#!/usr/bin/env python3
"""
Documentation Generation Script
================================

Generates API documentation using pdoc and creates a complete documentation site.

Usage:
    python scripts/generate_docs.py                    # Generate all docs
    python scripts/generate_docs.py --api-only         # Only generate API docs
    python scripts/generate_docs.py --serve            # Generate and serve locally
    python scripts/generate_docs.py --output custom/   # Custom output directory

Example:
    # Generate and open in browser
    python scripts/generate_docs.py --serve

    # Generate for deployment
    python scripts/generate_docs.py --output docs/html/
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


class DocumentationGenerator:
    """Generate comprehensive API documentation."""

    def __init__(self, output_dir: Path = None, verbose: bool = False):
        """Initialize documentation generator.

        Args:
            output_dir: Output directory for generated docs (default: docs/html)
            verbose: Enable verbose output

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.generate_all()
        """
        self.root_dir = Path(__file__).parent.parent
        self.output_dir = output_dir or (self.root_dir / "docs" / "html")
        self.verbose = verbose

        # Modules to document
        self.modules = [
            "agent",
            "client",
            "security",
            "prompts",
            "progress",
            "agents",
            "bridges",
            "daemon",
            "dashboard",
        ]

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled.

        Args:
            message: Message to log
        """
        if self.verbose:
            print(f"[DOCS] {message}")

    def generate_api_docs(self) -> bool:
        """Generate API documentation with pdoc.

        Returns:
            True if successful, False otherwise

        Raises:
            subprocess.CalledProcessError: If pdoc fails

        Example:
            >>> gen = DocumentationGenerator()
            >>> success = gen.generate_api_docs()
        """
        self.log("Generating API documentation with pdoc...")

        # Create output directory
        api_output = self.output_dir / "api"
        api_output.mkdir(parents=True, exist_ok=True)

        # Build pdoc command
        cmd = [
            sys.executable,
            "-m",
            "pdoc",
            "--html",
            "--output-dir",
            str(api_output),
            "--force",
        ]

        # Add all modules
        cmd.extend(self.modules)

        try:
            # Run pdoc
            result = subprocess.run(
                cmd,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=True,
            )

            if self.verbose and result.stdout:
                print(result.stdout)

            self.log(f"API docs generated in {api_output}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Error generating API docs: {e}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            return False

    def copy_markdown_docs(self) -> bool:
        """Copy Markdown documentation to output directory.

        Returns:
            True if successful, False otherwise

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.copy_markdown_docs()
        """
        self.log("Copying Markdown documentation...")

        docs_src = self.root_dir / "docs"
        docs_dest = self.output_dir

        # Ensure destination exists
        docs_dest.mkdir(parents=True, exist_ok=True)

        # Files to copy
        markdown_files = [
            "DEVELOPER_GUIDE.md",
            "BRIDGE_INTERFACE.md",
        ]

        # Copy main README
        readme_src = self.root_dir / "README.md"
        if readme_src.exists():
            shutil.copy2(readme_src, docs_dest / "README.md")
            self.log(f"Copied {readme_src.name}")

        # Copy markdown docs
        for filename in markdown_files:
            src = docs_src / filename
            if src.exists():
                shutil.copy2(src, docs_dest / filename)
                self.log(f"Copied {filename}")
            else:
                print(f"Warning: {filename} not found")

        return True

    def create_index(self) -> bool:
        """Create index.html landing page.

        Returns:
            True if successful

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.create_index()
        """
        self.log("Creating index.html...")

        index_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Dashboard Documentation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }

        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 60px 40px;
            text-align: center;
        }

        h1 {
            font-size: 3em;
            margin-bottom: 10px;
        }

        .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        .section {
            margin-bottom: 40px;
        }

        h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 2em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .card {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
        }

        .card h3 {
            color: #667eea;
            margin-bottom: 10px;
        }

        .card p {
            color: #6c757d;
            margin-bottom: 15px;
        }

        .card a {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.2s;
        }

        .card a:hover {
            background: #764ba2;
        }

        .feature-list {
            list-style: none;
            padding: 0;
        }

        .feature-list li {
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }

        .feature-list li:before {
            content: "✓ ";
            color: #667eea;
            font-weight: bold;
            margin-right: 10px;
        }

        footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #6c757d;
            border-top: 1px solid #e9ecef;
        }

        @media (max-width: 768px) {
            h1 {
                font-size: 2em;
            }

            .content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Agent Dashboard</h1>
            <p class="subtitle">Complete Documentation & API Reference</p>
        </header>

        <div class="content">
            <div class="section">
                <h2>📚 Documentation</h2>
                <div class="card-grid">
                    <div class="card">
                        <h3>Developer Guide</h3>
                        <p>Comprehensive guide for developers including setup, architecture, and common tasks.</p>
                        <a href="DEVELOPER_GUIDE.html">Read Guide →</a>
                    </div>

                    <div class="card">
                        <h3>Bridge Interface</h3>
                        <p>Specification and examples for AI provider bridge implementations.</p>
                        <a href="BRIDGE_INTERFACE.html">View Interface →</a>
                    </div>

                    <div class="card">
                        <h3>API Reference</h3>
                        <p>Auto-generated API documentation for all Python modules.</p>
                        <a href="api/index.html">Browse API →</a>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>🚀 Quick Start</h2>
                <ul class="feature-list">
                    <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
                    <li>Configure environment: <code>cp .env.example .env</code></li>
                    <li>Run agent: <code>python scripts/autonomous_agent_demo.py</code></li>
                    <li>Check the Developer Guide for detailed setup instructions</li>
                </ul>
            </div>

            <div class="section">
                <h2>🔧 Core Modules</h2>
                <div class="card-grid">
                    <div class="card">
                        <h3>agent.py</h3>
                        <p>Agent session logic and autonomous loop</p>
                        <a href="api/agent.html">Documentation →</a>
                    </div>

                    <div class="card">
                        <h3>client.py</h3>
                        <p>Claude SDK client configuration</p>
                        <a href="api/client.html">Documentation →</a>
                    </div>

                    <div class="card">
                        <h3>security.py</h3>
                        <p>Bash command validation and security hooks</p>
                        <a href="api/security.html">Documentation →</a>
                    </div>

                    <div class="card">
                        <h3>bridges/</h3>
                        <p>AI provider bridge implementations</p>
                        <a href="api/bridges/index.html">Documentation →</a>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>🌐 AI Provider Bridges</h2>
                <ul class="feature-list">
                    <li>OpenAI/ChatGPT - GPT-4o, o1, o3-mini, o4-mini</li>
                    <li>Google Gemini - 2.5 Flash, 2.5 Pro, 2.0 Flash</li>
                    <li>Groq - Ultra-fast LPU inference</li>
                    <li>KIMI - Ultra-long context (2M tokens)</li>
                    <li>Windsurf - Parallel coding via IDE</li>
                </ul>
            </div>
        </div>

        <footer>
            <p>&copy; 2026 Agent Dashboard Project | Built with ❤️ and Claude</p>
            <p>Documentation generated with pdoc</p>
        </footer>
    </div>
</body>
</html>
"""

        index_path = self.output_dir / "index.html"
        index_path.write_text(index_content)
        self.log(f"Created {index_path}")

        return True

    def convert_markdown_to_html(self) -> bool:
        """Convert Markdown files to HTML for web viewing.

        Returns:
            True if successful

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.convert_markdown_to_html()
        """
        self.log("Converting Markdown to HTML...")

        try:
            import markdown
        except ImportError:
            print("Warning: markdown package not installed, skipping HTML conversion")
            return False

        markdown_files = ["DEVELOPER_GUIDE.md", "BRIDGE_INTERFACE.md", "README.md"]

        for filename in markdown_files:
            md_path = self.output_dir / filename
            if not md_path.exists():
                continue

            html_path = self.output_dir / filename.replace(".md", ".html")

            # Read markdown
            md_content = md_path.read_text()

            # Convert to HTML
            html_body = markdown.markdown(
                md_content,
                extensions=["fenced_code", "tables", "toc", "codehilite"],
            )

            # Wrap in HTML template
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{filename.replace('.md', '')} - Agent Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #667eea;
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        code {{
            background: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
        }}
        pre {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background: #667eea;
            color: white;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .nav {{
            background: #f6f8fa;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 6px;
        }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html">← Back to Documentation Home</a>
    </div>
    {html_body}
</body>
</html>
"""

            html_path.write_text(html_content)
            self.log(f"Converted {filename} to HTML")

        return True

    def generate_all(self) -> bool:
        """Generate all documentation.

        Returns:
            True if all steps succeed

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.generate_all()
        """
        print("Generating documentation...")

        steps = [
            ("Generating API docs", self.generate_api_docs),
            ("Copying Markdown docs", self.copy_markdown_docs),
            ("Converting Markdown to HTML", self.convert_markdown_to_html),
            ("Creating index page", self.create_index),
        ]

        for step_name, step_func in steps:
            print(f"\n{step_name}...")
            if not step_func():
                print(f"Failed: {step_name}")
                return False

        print(f"\n✅ Documentation generated successfully!")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"🌐 Open in browser: file://{self.output_dir.absolute()}/index.html")

        return True

    def serve(self, port: int = 8000) -> None:
        """Serve documentation locally.

        Args:
            port: Port to serve on (default: 8000)

        Example:
            >>> gen = DocumentationGenerator()
            >>> gen.generate_all()
            >>> gen.serve()
        """
        import http.server
        import socketserver
        import os

        os.chdir(self.output_dir)

        Handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", port), Handler) as httpd:
            print(f"\n📡 Serving documentation at http://localhost:{port}")
            print(f"📂 Directory: {self.output_dir}")
            print("Press Ctrl+C to stop")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\nServer stopped")


def main():
    """Main entry point for documentation generation script.

    Example:
        $ python scripts/generate_docs.py
        $ python scripts/generate_docs.py --serve
        $ python scripts/generate_docs.py --output custom/
    """
    parser = argparse.ArgumentParser(
        description="Generate API documentation for Agent Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate all documentation:
    python scripts/generate_docs.py

  Generate and serve locally:
    python scripts/generate_docs.py --serve

  Generate to custom directory:
    python scripts/generate_docs.py --output docs/html/

  Only generate API docs:
    python scripts/generate_docs.py --api-only
        """,
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: docs/html)",
    )

    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Only generate API documentation",
    )

    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve documentation locally after generation",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for local server (default: 8000)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Create generator
    gen = DocumentationGenerator(output_dir=args.output, verbose=args.verbose)

    # Generate documentation
    if args.api_only:
        success = gen.generate_api_docs()
    else:
        success = gen.generate_all()

    if not success:
        sys.exit(1)

    # Serve if requested
    if args.serve:
        gen.serve(port=args.port)


if __name__ == "__main__":
    main()
