"""CLI control package for Shieldstral Guardrail."""

def main():
    from .guardctl import main as _main
    return _main()

__all__ = ["main"]
