"""
Quick validation script for KAN-50 agent setup
Tests basic structure without requiring package installation
"""

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent


def validate_files():
    """Validate all required files exist"""
    print("Validating file structure...")
    required_files = [
        "requirements.txt",
        "main.py",
        ".env.example",
        ".gitignore",
        "__init__.py",
        "README.md",
        "test_agent_setup.py",
    ]

    all_exist = True
    for filename in required_files:
        filepath = AGENT_DIR / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} MISSING")
            all_exist = False

    return all_exist


def validate_requirements():
    """Validate requirements.txt has necessary packages"""
    print("\nValidating requirements.txt...")
    requirements_path = AGENT_DIR / "requirements.txt"

    with open(requirements_path, "r") as f:
        content = f.read()

    required_packages = [
        "pydantic-ai",
        "pydantic>=2.0.0",
        "fastapi>=0.100.0",
        "uvicorn",
        "python-dotenv",
        "pytest",
        "httpx",
    ]

    all_found = True
    for package in required_packages:
        if package.split(">=")[0] in content or package.split("[")[0] in content:
            print(f"  ✓ {package}")
        else:
            print(f"  ✗ {package} MISSING")
            all_found = False

    return all_found


def validate_main_py():
    """Validate main.py has required components"""
    print("\nValidating main.py...")
    main_path = AGENT_DIR / "main.py"

    with open(main_path, "r") as f:
        content = f.read()

    required_components = [
        ("FastAPI import", "from fastapi import FastAPI"),
        ("CORS middleware", "CORSMiddleware"),
        ("Health endpoint", "def health_check"),
        ("AG-UI endpoint", "/ag-ui/stream"),
        ("dotenv", "load_dotenv"),
        ("Lifespan manager", "lifespan"),
        ("Root endpoint", "app.get(\"/\")"),
        ("Error handlers", "exception_handler"),
        ("Uvicorn runner", "uvicorn.run"),
    ]

    all_found = True
    for name, search_string in required_components:
        if search_string in content:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} MISSING")
            all_found = False

    return all_found


def validate_env_example():
    """Validate .env.example has required variables"""
    print("\nValidating .env.example...")
    env_path = AGENT_DIR / ".env.example"

    with open(env_path, "r") as f:
        content = f.read()

    required_vars = [
        "ENVIRONMENT",
        "BACKEND_PORT",
        "FRONTEND_PORT",
    ]

    all_found = True
    for var in required_vars:
        if var in content:
            print(f"  ✓ {var}")
        else:
            print(f"  ✗ {var} MISSING")
            all_found = False

    return all_found


def validate_gitignore():
    """Validate .gitignore excludes necessary files"""
    print("\nValidating .gitignore...")
    gitignore_path = AGENT_DIR / ".gitignore"

    with open(gitignore_path, "r") as f:
        content = f.read()

    required_excludes = [
        ("venv/", ["venv/"]),
        (".env", [".env"]),
        ("__pycache__", ["__pycache__"]),
        ("*.pyc (or *.py[cod])", ["*.pyc", "*.py[cod]"]),
    ]

    all_found = True
    for name, patterns in required_excludes:
        found = any(pattern in content for pattern in patterns)
        if found:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name} MISSING")
            all_found = False

    return all_found


def validate_test_file():
    """Validate test file has comprehensive tests"""
    print("\nValidating test_agent_setup.py...")
    test_path = AGENT_DIR / "test_agent_setup.py"

    with open(test_path, "r") as f:
        content = f.read()

    required_test_classes = [
        "TestDirectoryStructure",
        "TestRequirementsTxt",
        "TestFastAPIApp",
        "TestHealthEndpoint",
        "TestAGUIStreamEndpoint",
        "TestCORSConfiguration",
    ]

    all_found = True
    for test_class in required_test_classes:
        if test_class in content:
            print(f"  ✓ {test_class}")
        else:
            print(f"  ✗ {test_class} MISSING")
            all_found = False

    # Count test methods
    test_methods = content.count("def test_")
    print(f"  ✓ Total test methods: {test_methods}")

    return all_found and test_methods > 20


def validate_code_syntax():
    """Validate Python syntax is correct"""
    print("\nValidating Python syntax...")

    files_to_check = ["main.py", "__init__.py", "test_agent_setup.py", "validate_setup.py"]

    all_valid = True
    for filename in files_to_check:
        filepath = AGENT_DIR / filename
        try:
            with open(filepath, "r") as f:
                code = f.read()
            compile(code, filepath, "exec")
            print(f"  ✓ {filename} - valid syntax")
        except SyntaxError as e:
            print(f"  ✗ {filename} - syntax error: {e}")
            all_valid = False

    return all_valid


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("KAN-50: Agent Backend Setup Validation")
    print("=" * 60)

    results = {
        "File Structure": validate_files(),
        "Requirements.txt": validate_requirements(),
        "Main.py Components": validate_main_py(),
        ".env.example": validate_env_example(),
        ".gitignore": validate_gitignore(),
        "Test File": validate_test_file(),
        "Python Syntax": validate_code_syntax(),
    }

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check:.<40} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All validation checks passed!")
        print("\nSetup complete - ready for installation:")
        print("1. Create virtual environment: python3 -m venv venv")
        print("2. Activate it: source venv/bin/activate")
        print("3. Install dependencies: pip install -r requirements.txt")
        print("4. Run tests: pytest test_agent_setup.py -v")
        print("5. Start server: python main.py")
        print("\nThe backend will run on: http://localhost:8000")
        print("API docs will be at: http://localhost:8000/docs")
        return 0
    else:
        print("\n✗ Some validation checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
