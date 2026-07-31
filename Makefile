# Connectify - SSH Session Manager (Development)

.PHONY: help setup dev ui build clean dev-install release

help:
	@echo "Connectify - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make setup         Set up development environment"
	@echo "  make ui            Run the web interface in the foreground"
	@echo "  make dev           Alias for 'make ui'"
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

dev: ui

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

# Archive named for the machine you're on - CI builds one per architecture
ARCH := $(shell uname -m | sed 's/x86_64/amd64/')

release: build
	@echo "📦 Creating release archive for $(ARCH)..."
	@cd dist && tar -czf connectify-macos-$(ARCH).tar.gz connectify/
	@echo "✅ Release archive created: ./dist/connectify-macos-$(ARCH).tar.gz"
	@echo ""
	@echo "To publish a release (builds both arm64 and amd64):"
	@echo "  • Push a version tag:  git tag v2.0.1 && git push origin v2.0.1"
	@echo "  • Or run the 'Build and Release' workflow manually with a version"

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf build/ dist/ __pycache__/ *.egg-info/ .pytest_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete."