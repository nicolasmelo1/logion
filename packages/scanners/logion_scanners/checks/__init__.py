"""Agent scanner checks registry."""

from logion_scanners.checks.dangerous_commands import (
    DangerousCommandsCheck,
)
from logion_scanners.checks.env_harvesting import EnvHarvestingCheck
from logion_scanners.checks.file_structure import FileStructureCheck
from logion_scanners.checks.file_type import FileTypeCheck
from logion_scanners.checks.network_audit import NetworkAuditCheck
from logion_scanners.checks.obfuscation import ObfuscationCheck
from logion_scanners.checks.prompt_injection import (
    PromptInjectionCheck,
)
from logion_scanners.checks.runtime_install_attempt import (
    RuntimeInstallAttemptCheck,
)
from logion_scanners.checks.secrets_detection import (
    SecretsDetectionCheck,
)

# Ordered registry of all agent scanner checks.
ALL_CHECKS: list[type] = [
    FileStructureCheck,
    FileTypeCheck,
    DangerousCommandsCheck,
    RuntimeInstallAttemptCheck,
    SecretsDetectionCheck,
    EnvHarvestingCheck,
    NetworkAuditCheck,
    ObfuscationCheck,
    PromptInjectionCheck,
]

__all__ = ["ALL_CHECKS"]
