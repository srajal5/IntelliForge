"""
AI Intelligence Pipeline - Application Entry Point

Delegates to the CLI application defined in src.cli.app.
Run with: python -m src.main [COMMAND]
"""

from src.cli.app import main

if __name__ == "__main__":
    main()
