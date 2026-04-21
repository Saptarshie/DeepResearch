"""OmegaResearcher — Autonomous Research Intelligence System."""
from omega_researcher.config import Config

__all__ = ["Config"]


def deep_research(*args, **kwargs):
    """Lazy import to avoid circular deps during early development."""
    from omega_researcher.orchestrator import deep_research as _dr
    return _dr(*args, **kwargs)
