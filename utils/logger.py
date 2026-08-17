"""utils/logger.py — Coloured logging with Rich."""
import logging
from rich.logging import RichHandler
from rich.console import Console

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%H:%M:%S]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
)
log = logging.getLogger("job_scanner")
