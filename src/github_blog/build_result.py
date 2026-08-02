"""Structured build result and diagnostics.

Core build code returns ``BuildResult`` rather than calling ``sys.exit``.
Only ``run_cli()`` maps final failure to process exit status.  Diagnostics
carry stable codes, severity, optional Issue number, and field so that the
caller can report all errors in one run.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Allowed severity values for :class:`Diagnostic`.
ALLOWED_SEVERITIES: frozenset[str] = frozenset({"error", "warning"})


@dataclass(frozen=True)
class Diagnostic:
    """A single diagnostic message from the build process.

    Attributes:
        severity: ``"error"`` or ``"warning"``.  Errors prevent output
            replacement; warnings do not.
        code: Stable machine-readable code (e.g. ``"FETCH_FAILED"``).
        message: Human-readable description.
        issue_number: GitHub Issue number when applicable.
        field: Field name when applicable.
    """

    severity: str
    code: str
    message: str
    issue_number: int | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"Diagnostic.severity must be one of {sorted(ALLOWED_SEVERITIES)}, "
                f"got {self.severity!r}"
            )


@dataclass(frozen=True)
class BuildResult:
    """Structured result of a build attempt.

    Attributes:
        success: Whether the build completed and output was published.
        diagnostics: Tuple of diagnostic messages accumulated during the
            build.  Empty when the build succeeds without warnings.
    """

    success: bool
    diagnostics: tuple[Diagnostic, ...] = ()
