# Documentation Deployment Guide

This guide explains how to deploy the Agent Dashboard documentation to various hosting platforms.

## Table of Contents

1. [GitHub Pages (Recommended)](#github-pages)
2. [ReadTheDocs](#readthedocs)
3. [Netlify](#netlify)
4. [Local Deployment](#local-deployment)

## GitHub Pages

GitHub Pages is the recommended hosting solution for this documentation.

### Automatic Deployment (via GitHub Actions)

The repository includes a GitHub Actions workflow that automatically builds and deploys documentation on every push to `main`.

**Setup:**

1. Enable GitHub Pages in your repository:
   - Go to Settings → Pages
   - Source: GitHub Actions
   - Save

2. Push to main branch:
   ```bash
   git add .
   git commit -m "Update documentation"
   git push origin main
   ```

3. The workflow will automatically:
   - Install dependencies
   - Generate API docs with pdoc
   - Convert Markdown to HTML
   - Deploy to GitHub Pages

4. Access your docs at: `https://<username>.github.io/<repository>/`

### Manual Deployment

If you prefer manual deployment:

1. Generate documentation:
   ```bash
   python scripts/generate_docs.py
   ```

2. Create `gh-pages` branch:
   ```bash
   git checkout --orphan gh-pages
   git rm -rf .
   cp -r docs/html/* .
   git add .
   git commit -m "Deploy documentation"
   git push origin gh-pages
   ```

3. Configure GitHub Pages:
   - Settings → Pages
   - Source: Deploy from branch
   - Branch: gh-pages
   - Folder: / (root)

## ReadTheDocs

ReadTheDocs provides advanced documentation hosting with versioning.

### Setup

1. Create `.readthedocs.yml`:
   ```yaml
   version: 2

   build:
     os: ubuntu-22.04
     tools:
       python: "3.11"

   python:
     install:
       - requirements: requirements.txt
       - method: pip
         path: .

   sphinx:
     configuration: docs/conf.py
   ```

2. Create Sphinx configuration (if using Sphinx instead of pdoc):
   ```bash
   mkdir -p docs
   cd docs
   sphinx-quickstart
   ```

3. Connect repository to ReadTheDocs:
   - Go to https://readthedocs.org
   - Import a Project
   - Select your GitHub repository
   - Build documentation

4. Access docs at: `https://<project>.readthedocs.io`

## Netlify

Netlify provides fast global CDN hosting.

### Setup

1. Create `netlify.toml`:
   ```toml
   [build]
     command = "python scripts/generate_docs.py"
     publish = "docs/html"

   [[redirects]]
     from = "/*"
     to = "/index.html"
     status = 200
   ```

2. Deploy:

   **Option A: Netlify CLI**
   ```bash
   npm install -g netlify-cli
   netlify deploy --prod --dir=docs/html
   ```

   **Option B: Git Integration**
   - Go to https://app.netlify.com
   - New site from Git
   - Select repository
   - Build command: `python scripts/generate_docs.py`
   - Publish directory: `docs/html`

3. Access docs at: `https://<site-name>.netlify.app`

## Local Deployment

For development and testing.

### Method 1: Python HTTP Server

```bash
# Generate documentation
python scripts/generate_docs.py

# Serve locally
cd docs/html
python -m http.server 8000

# Open in browser
open http://localhost:8000
```

### Method 2: Using the generation script

```bash
# Generate and serve in one command
python scripts/generate_docs.py --serve

# Custom port
python scripts/generate_docs.py --serve --port 8080
```

### Method 3: Live reload (for development)

```bash
# Install live-server
npm install -g live-server

# Generate docs
python scripts/generate_docs.py

# Serve with auto-reload
cd docs/html
live-server
```

## Updating Documentation

### Automatic Updates

Documentation is automatically rebuilt when:
- GitHub Actions: On every push to `main`
- ReadTheDocs: On every push to any branch
- Netlify: On every push to connected branch

### Manual Updates

1. Update source files (docstrings, markdown docs)
2. Regenerate documentation:
   ```bash
   python scripts/generate_docs.py
   ```
3. Deploy using your chosen method

## Keeping Docs in Sync with Code

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Regenerate docs before commit

echo "Regenerating documentation..."
python scripts/generate_docs.py --api-only

# Add generated docs to commit
git add docs/html/api/

echo "Documentation updated"
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

### CI/CD Integration

The GitHub Actions workflow automatically:
1. Checks out code
2. Installs dependencies
3. Generates documentation
4. Deploys to GitHub Pages

See `.github/workflows/docs.yml` for details.

### Documentation Versioning

For maintaining multiple versions:

**GitHub Pages:**
```bash
# Generate docs for v1.0
python scripts/generate_docs.py --output docs/html/v1.0

# Generate docs for v2.0
python scripts/generate_docs.py --output docs/html/v2.0

# Create version selector in index.html
```

**ReadTheDocs:**
- Automatically builds docs for each branch/tag
- Provides version selector UI
- Configure in RTD dashboard

## Troubleshooting

### Build Failures

**Import errors during pdoc generation:**
```bash
# Set PYTHONPATH to include scripts
export PYTHONPATH=/path/to/project/scripts:$PYTHONPATH
python -m pdoc -o docs/html/api <modules>
```

**Missing dependencies:**
```bash
pip install -r requirements.txt
pip install pdoc markdown
```

### GitHub Actions Failures

Check the workflow file:
```bash
cat .github/workflows/docs.yml
```

View logs in GitHub Actions tab.

### Broken Links

After deployment, check for broken links:
```bash
# Install linkchecker
pip install linkchecker

# Check deployed site
linkchecker https://your-site.github.io
```

## Best Practices

1. **Version Documentation**: Tag releases and build versioned docs
2. **Automated Builds**: Use CI/CD for consistent builds
3. **Link Checking**: Validate links before deployment
4. **Preview Deploys**: Use Netlify/Vercel preview deploys for PRs
5. **Search Integration**: Enable search in documentation
6. **Analytics**: Add Google Analytics or similar
7. **Custom Domain**: Use custom domain for professional appearance

## Custom Domain Setup

### GitHub Pages

1. Add CNAME file:
   ```bash
   echo "docs.yourdomain.com" > docs/html/CNAME
   ```

2. Configure DNS:
   ```
   CNAME docs.yourdomain.com → <username>.github.io
   ```

3. Enable HTTPS in GitHub Pages settings

### Netlify

1. Add custom domain in Netlify dashboard
2. Update DNS records as instructed
3. HTTPS is automatic

## Security

- Enable HTTPS (automatic on GitHub Pages, Netlify, RTD)
- Use Content Security Policy headers
- Regularly update dependencies
- Scan for vulnerabilities: `pip audit`

## Maintenance

### Regular Updates

Schedule regular documentation updates:
- Review and update examples monthly
- Update API docs with each release
- Check and fix broken links quarterly
- Update dependencies regularly

### Monitoring

Monitor documentation:
- Page load times
- Broken links
- User feedback
- Search analytics

## Additional Resources

- [GitHub Pages Documentation](https://docs.github.com/pages)
- [ReadTheDocs Documentation](https://docs.readthedocs.io/)
- [Netlify Documentation](https://docs.netlify.com/)
- [pdoc Documentation](https://pdoc.dev/)

## Support

For deployment issues:
1. Check the troubleshooting section above
2. Review platform-specific documentation
3. Check CI/CD logs for errors
4. Open an issue in the repository
