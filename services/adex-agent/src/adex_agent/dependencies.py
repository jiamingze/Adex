"""Process-scoped dependencies constructed only at the composition boundary."""

from adex_kernel.core import Core
from adex_agent.execution.runtime import Runtime

core = Core("agent")
runtime = Runtime(core)
