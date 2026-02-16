#!/usr/bin/env python3
"""Convert markdown docs to HTML and prepare documentation site."""

import shutil
from pathlib import Path
import markdown

def main():
    # Create docs directory
    docs_dir = Path('docs/html')
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Copy markdown docs
    for file in ['DEVELOPER_GUIDE.md', 'BRIDGE_INTERFACE.md']:
        src = Path('docs') / file
        if src.exists():
            shutil.copy2(src, docs_dir / file)
            print(f'Copied {file}')

    # Convert to HTML
    for file in ['DEVELOPER_GUIDE.md', 'BRIDGE_INTERFACE.md']:
        md_path = docs_dir / file
        if md_path.exists():
            html_path = docs_dir / file.replace('.md', '.html')
            md_content = md_path.read_text()
            html_body = markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'toc'])
            html_content = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{file.replace('.md', '')}</title>
<style>
body {{font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6;}}
code {{background: #f6f8fa; padding: 2px 6px; border-radius: 3px;}}
pre {{background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto;}}
pre code {{background: none; padding: 0;}}
h1, h2, h3 {{color: #667eea;}}
a {{color: #667eea;}}
table {{border-collapse: collapse; width: 100%;}}
th, td {{border: 1px solid #ddd; padding: 12px;}}
th {{background: #667eea; color: white;}}
</style></head><body>
<div style="background: #f6f8fa; padding: 10px; margin-bottom: 20px; border-radius: 6px;">
<a href="index.html">← Back to Documentation Home</a>
</div>
{html_body}
</body></html>'''
            html_path.write_text(html_content)
            print(f'Converted {file} to HTML')

    # Create index.html
    create_index(docs_dir)

    print('Documentation prepared successfully!')
    print(f'Output: {docs_dir.absolute()}')

def create_index(docs_dir):
    """Create documentation index page."""
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Dashboard Documentation</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
        h1 { font-size: 3em; margin-bottom: 10px; }
        .subtitle { font-size: 1.2em; opacity: 0.9; }
        .content { padding: 40px; }
        .section { margin-bottom: 40px; }
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
        .card h3 { color: #667eea; margin-bottom: 10px; }
        .card p { color: #6c757d; margin-bottom: 15px; }
        .card a {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.2s;
        }
        .card a:hover { background: #764ba2; }
        .feature-list { list-style: none; padding: 0; }
        .feature-list li { padding: 10px 0; border-bottom: 1px solid #e9ecef; }
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
                        <h3>prompts.py</h3>
                        <p>Prompt template management</p>
                        <a href="api/prompts.html">Documentation →</a>
                    </div>
                </div>
            </div>
        </div>
        <footer>
            <p>&copy; 2026 Agent Dashboard Project | Built with ❤️ and Claude</p>
            <p>Documentation generated with pdoc</p>
        </footer>
    </div>
</body>
</html>'''

    (docs_dir / 'index.html').write_text(index_html)
    print('Created index.html')

if __name__ == '__main__':
    main()
