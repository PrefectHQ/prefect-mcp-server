mod scenarios

# Check for uv installation
check-uv:
    #!/usr/bin/env sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is not installed or not found in expected locations."
        case "$(uname)" in
            "Darwin")
                echo "To install uv on macOS, run one of:"
                echo "• brew install uv"
                echo "• curl -LsSf https://astral.sh/uv/install.sh | sh"
                ;;
            "Linux")
                echo "To install uv, run:"
                echo "• curl -LsSf https://astral.sh/uv/install.sh | sh"
                ;;
            *)
                echo "To install uv, visit: https://github.com/astral-sh/uv"
                ;;
        esac
        exit 1
    fi

# Get setup as a new developer
setup: check-uv
    uv run pre-commit install

# Run tests
test:
    uv run --frozen pytest -xvs tests

# Run linting
lint:
    uv run --frozen ruff check --fix

# Run ty type checker on all files
typecheck:
    uv run --frozen ty check

# Copy context to clipboard
copy-context:
    uvx --with-editable . --refresh-package copychat copychat@latest src/ README.md -v