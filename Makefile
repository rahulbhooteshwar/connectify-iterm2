# Connectify - SSH Session Manager (Development)

.PHONY: help setup dev ui build clean dev-install release

help:
	@echo "Connectify - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make setup         Set up development environment"
	@echo "  make dev           Run in development mode (terminal)"
	@echo "  make ui            Launch web interface"
	@echo ""
	@echo "Building:"
	@echo "  make build         Build standalone executable"
	@echo "  make dev-install   Build and install locally for testing"
	@echo "  make release       Create release archive"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         Clean build artifacts"
	@echo ""
	@echo "Note: Users should install via:"
	@echo "  curl -LsSf https://raw.githubusercontent.com/rahulbhooteshwar/iterm2-ssh-session-manager/main/install.sh | sh"
	@echo ""

setup:
	@echo "🔧 Setting up development environment with uv..."
	@uv sync
	@echo "✅ Environment setup complete!"

dev:
	@echo "🚀 Running in development mode..."
	@uv run python main.py

ui:
	@echo "🌐 Launching web interface..."
	@uv run python main.py --ui

build:
	@echo "📦 Building Connectify executable..."
	@uv run pyinstaller connectify.spec
	@echo "✅ Executable built: ./dist/connectify/connectify"

dev-install: build
	@echo "🚀 Installing locally for development..."
	@./dev-install.sh

release: build
	@echo "📦 Creating release archive..."
	@cd dist && tar -czf connectify-macos-arm64.tar.gz connectify/
	@echo "✅ Release archive created: ./dist/connectify-macos-arm64.tar.gz"
	@echo ""
	@echo "To create a GitHub release:"
	@echo "  1. Push a version tag: git tag v1.0.0 && git push origin v1.0.0"
	@echo "  2. GitHub Actions will automatically build and publish"

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf build/ dist/ __pycache__/ *.egg-info/ .pytest_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete."