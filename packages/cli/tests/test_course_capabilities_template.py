# SPDX-License-Identifier: MIT
"""Round-trip tests for the bundled capability manifest scaffold.

The scaffold ships in ``cli/templates/`` and is exposed via
``logion courses capabilities scaffold``.  These tests guarantee that:

1. The scaffold as-shipped (all examples commented out, only
   ``version: 1`` uncommented) parses successfully through the same
   validator the CLI and server use.
2. Uncommenting every example value at once also produces a valid
   manifest — which catches the case where a constraint changes
   in the validator but the example in the scaffold drifts.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

import pytest

from cli._course_capabilities import (
    CAPABILITY_MANIFEST_PATH,
    CapabilityManifestError,
    load_and_validate_capability_manifest,
)
from cli.commands.courses.capabilities import (
    CAPABILITIES_TEMPLATE_FILENAME,
)

TEMPLATE_TEXT = (
    resources
    .files("cli.templates")
    .joinpath(CAPABILITIES_TEMPLATE_FILENAME)
    .read_text(encoding="utf-8")
)


def _bundle_with_manifest(tmp_path: Path, manifest_text: str) -> Path:
    """Write *manifest_text* into a fresh course bundle dir."""
    bundle = tmp_path / "bundle"
    (bundle / CAPABILITY_MANIFEST_PATH.parent).mkdir(parents=True)
    (bundle / CAPABILITY_MANIFEST_PATH).write_text(
        manifest_text, encoding="utf-8"
    )
    return bundle


def _uncomment_examples(text: str) -> str:
    """Uncomment every YAML example line in the scaffold.

    A YAML example line is ``# `` followed by either a key (``foo:``)
    or a list item (``- value``), possibly with inner indentation that
    represents nesting.  Prose comments are left alone.
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("# "):
            body = stripped[2:]
            if re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*:|^\s*- ", body):
                indent = line[: len(line) - len(stripped)]
                out.append(indent + body)
                continue
        out.append(line)
    return "\n".join(out) + "\n"


class TestCapabilitiesScaffold:
    def test_template_file_exists(self) -> None:
        assert TEMPLATE_TEXT.startswith("# course/capabilities.yaml"), (
            "Scaffold header changed; update tests to match."
        )

    def test_as_shipped_parses_as_empty_manifest(self, tmp_path: Path) -> None:
        """The shipped scaffold (only version: 1 uncommented) is valid."""
        bundle = _bundle_with_manifest(tmp_path, TEMPLATE_TEXT)
        manifest = load_and_validate_capability_manifest(bundle)
        assert manifest["version"] == 1
        assert manifest["tools"] == []
        assert manifest["network"] == {"allow_domains": []}
        assert manifest["filesystem"] == {"read": [], "write": []}
        assert manifest["secrets"] == {"env": []}
        assert manifest["human_approval"] == {"required": False}

    def test_fully_uncommented_scaffold_is_valid(self, tmp_path: Path) -> None:
        """All example values, when uncommented, pass the validator.

        This guards against the scaffold's examples drifting from the
        validator's accepted shape.
        """
        uncommented = _uncomment_examples(TEMPLATE_TEXT)
        bundle = _bundle_with_manifest(tmp_path, uncommented)
        manifest = load_and_validate_capability_manifest(bundle)
        # Spot-check that the examples actually landed in the manifest.
        assert "file" in manifest["tools"]
        assert "web" in manifest["tools"]
        assert "api.example.com" in manifest["network"]["allow_domains"]
        assert "OPENAI_API_KEY" in manifest["secrets"]["env"]
        assert manifest["human_approval"]["required"] is True

    def test_template_documents_closed_tool_enum(self) -> None:
        """The scaffold must list every allowed tool name verbatim."""
        from cli._course_capabilities import ALLOWED_TOOLS

        for tool in ALLOWED_TOOLS:
            assert tool in TEMPLATE_TEXT, f"Scaffold missing tool name: {tool}"

    def test_template_documents_env_regex(self) -> None:
        """The scaffold must quote the env-var regex verbatim."""
        assert "^[A-Z_][A-Z0-9_]*$" in TEMPLATE_TEXT

    def test_template_documents_runtime_fields(self) -> None:
        """The scaffold must mention every runtime.requires field."""
        # The template uses YAML nesting under `runtime:` → `requires:`,
        # so we check for the field keys plus the runtime/install
        # section headers rather than dotted paths.
        for token in (
            "runtime:",
            "requires:",
            "install:",
            "# env —",
            "# bins —",
            "# any_bins —",
            "# config —",
            "# os —",
            "# software —",
        ):
            assert token in TEMPLATE_TEXT, (
                f"Scaffold missing runtime token: {token}"
            )

    def test_template_documents_install_warning(self) -> None:
        """The scaffold must warn that install commands are never auto-run."""
        assert "never auto-run" in TEMPLATE_TEXT.lower()

    def test_template_documents_secrets_vs_runtime_env_distinction(
        self,
    ) -> None:
        """The scaffold must explain secrets.env vs runtime.requires.env."""
        assert "secrets.env" in TEMPLATE_TEXT
        # The template explains the permission vs dependency distinction.
        assert "permission" in TEMPLATE_TEXT.lower()
        assert "dependency" in TEMPLATE_TEXT.lower()

    def test_template_documents_install_kinds(self) -> None:
        """The scaffold must list every INSTALL_KINDS enum value."""
        from cli._course_capabilities import INSTALL_KINDS

        for kind in INSTALL_KINDS:
            assert kind in TEMPLATE_TEXT, (
                f"Scaffold missing install kind: {kind}"
            )


class TestScaffoldCommand:
    def test_scaffold_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        from cli.main import main

        rc = main(["courses", "capabilities", "scaffold"])
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out.startswith("# course/capabilities.yaml")

    def test_scaffold_to_bundle_dir(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from cli.main import main

        bundle = tmp_path / "new-course"
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--bundle-dir",
            str(bundle),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        written = bundle / CAPABILITY_MANIFEST_PATH
        assert written.is_file()
        assert "Wrote scaffold to" in captured.out
        # File should round-trip through the validator.
        manifest = load_and_validate_capability_manifest(bundle)
        assert manifest["version"] == 1

    def test_scaffold_refuses_overwrite_without_force(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from cli.main import main

        bundle = tmp_path / "bundle"
        (bundle / CAPABILITY_MANIFEST_PATH.parent).mkdir(parents=True)
        (bundle / CAPABILITY_MANIFEST_PATH).write_text(
            "version: 1\n", encoding="utf-8"
        )
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--bundle-dir",
            str(bundle),
        ])
        captured = capsys.readouterr()
        assert rc == 2
        assert "Refusing to overwrite" in captured.err

    def test_scaffold_force_replaces_existing(self, tmp_path: Path) -> None:
        from cli.main import main

        bundle = tmp_path / "bundle"
        (bundle / CAPABILITY_MANIFEST_PATH.parent).mkdir(parents=True)
        existing = bundle / CAPABILITY_MANIFEST_PATH
        existing.write_text("garbage: nope\n", encoding="utf-8")
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--bundle-dir",
            str(bundle),
            "--force",
        ])
        assert rc == 0
        assert "version: 1" in existing.read_text(encoding="utf-8")
        # And the rewritten manifest passes the validator.
        manifest = load_and_validate_capability_manifest(bundle)
        assert manifest["version"] == 1


class TestScaffoldFromSkill:
    """Tests for ``--from-skill`` seeding the scaffold."""

    def _skill_md(
        self,
        tmp_path: Path,
        frontmatter: str,
        body: str = "# Skill\n",
    ) -> Path:
        skill = tmp_path / "SKILL.md"
        skill.write_text(
            f"---\n{frontmatter}---\n{body}",
            encoding="utf-8",
        )
        return skill

    def test_from_skill_writes_manifest_to_bundle(
        self, tmp_path: Path
    ) -> None:
        from cli.main import main

        skill = self._skill_md(
            tmp_path,
            "metadata:\n"
            "  logion:\n"
            "    version: 1\n"
            '    summary: "From skill."\n'
            "    tools:\n"
            "      - file\n",
        )
        bundle = tmp_path / "course"
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--from-skill",
            str(skill),
            "--bundle-dir",
            str(bundle),
        ])
        assert rc == 0
        written = bundle / CAPABILITY_MANIFEST_PATH
        assert written.is_file()
        manifest = load_and_validate_capability_manifest(bundle)
        assert manifest["version"] == 1
        assert manifest["summary"] == "From skill."
        assert manifest["tools"] == ["file"]

    def test_from_skill_prints_to_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from cli.main import main

        skill = self._skill_md(
            tmp_path,
            "metadata:\n"
            "  logion:\n"
            "    version: 1\n"
            '    summary: "Stdout skill."\n',
        )
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--from-skill",
            str(skill),
        ])
        captured = capsys.readouterr()
        assert rc == 0
        assert "version: 1" in captured.out
        assert "Stdout skill." in captured.out

    def test_from_skill_no_metadata_logion_returns_exit_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from cli.main import main

        skill = self._skill_md(
            tmp_path,
            "metadata:\n  other: true\n",
        )
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--from-skill",
            str(skill),
        ])
        captured = capsys.readouterr()
        assert rc == 2
        assert "no metadata.logion" in captured.err

    def test_from_skill_refuses_overwrite_without_force(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from cli.main import main

        skill = self._skill_md(
            tmp_path,
            "metadata:\n  logion:\n    version: 1\n",
        )
        bundle = tmp_path / "course"
        (bundle / CAPABILITY_MANIFEST_PATH.parent).mkdir(parents=True)
        (bundle / CAPABILITY_MANIFEST_PATH).write_text(
            "version: 1\n", encoding="utf-8"
        )
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--from-skill",
            str(skill),
            "--bundle-dir",
            str(bundle),
        ])
        captured = capsys.readouterr()
        assert rc == 2
        assert "Refusing to overwrite" in captured.err

    def test_from_skill_force_overwrites(self, tmp_path: Path) -> None:
        from cli.main import main

        skill = self._skill_md(
            tmp_path,
            'metadata:\n  logion:\n    version: 1\n    summary: "Forced."\n',
        )
        bundle = tmp_path / "course"
        (bundle / CAPABILITY_MANIFEST_PATH.parent).mkdir(parents=True)
        (bundle / CAPABILITY_MANIFEST_PATH).write_text(
            "garbage: nope\n", encoding="utf-8"
        )
        rc = main([
            "courses",
            "capabilities",
            "scaffold",
            "--from-skill",
            str(skill),
            "--bundle-dir",
            str(bundle),
            "--force",
        ])
        assert rc == 0
        manifest = load_and_validate_capability_manifest(bundle)
        assert manifest["summary"] == "Forced."


class TestScaffoldFailureModes:
    def test_unknown_top_level_key_still_rejected(
        self, tmp_path: Path
    ) -> None:
        """Sanity: validator rejects anything outside the documented schema."""
        bundle = _bundle_with_manifest(tmp_path, "version: 1\nbogus: true\n")
        with pytest.raises(CapabilityManifestError):
            load_and_validate_capability_manifest(bundle)
