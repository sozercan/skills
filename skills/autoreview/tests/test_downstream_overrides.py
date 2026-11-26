#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "autoreview"
LOADER = SourceFileLoader("autoreview_downstream_test_target", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
AUTOREVIEW = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(AUTOREVIEW)


class DownstreamOverrideTests(unittest.TestCase):
    def reviewer_for(self, *args: str):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            sys, "argv", ["autoreview", *args]
        ):
            return AUTOREVIEW.reviewer_args(AUTOREVIEW.parse_args())[0]

    def test_model_and_reasoning_defaults(self) -> None:
        codex = self.reviewer_for()
        codex_no_fallback = self.reviewer_for("--codex-no-fallback")
        claude = self.reviewer_for("--engine", "claude")

        self.assertEqual(
            (codex.model, codex.fallback_model, codex.thinking),
            ("gpt-6.2-sol", "gpt-6.1-sol", "high"),
        )
        self.assertIsNone(codex_no_fallback.fallback_model)
        self.assertEqual((claude.model, claude.thinking), ("claude-opus-5-5", "high"))

        for invalid_effort in ("none", "minimal"):
            with self.assertRaises(SystemExit):
                self.reviewer_for("--thinking", invalid_effort)

    def test_only_external_codex_base_url_uses_http_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo = root / "repo"
            repo.mkdir()
            external_home = root / "host" / ".codex"
            external_home.mkdir(parents=True)
            (external_home / "config.toml").write_text(
                'openai_base_url = "https://codex-proxy.example/v1"\n',
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ, {"CODEX_HOME": str(external_home)}, clear=True
            ):
                self.assertEqual(
                    AUTOREVIEW.codex_auth_config_flags(repo),
                    [
                        "-c",
                        'model_provider="autoreview_openai_http"',
                        "-c",
                        'model_providers.autoreview_openai_http.name="OpenAI"',
                        "-c",
                        'model_providers.autoreview_openai_http.base_url="https://codex-proxy.example/v1"',
                        "-c",
                        'model_providers.autoreview_openai_http.wire_api="responses"',
                        "-c",
                        "model_providers.autoreview_openai_http.requires_openai_auth=true",
                        "-c",
                        "model_providers.autoreview_openai_http.supports_websockets=false",
                        "-c",
                        "model_providers.autoreview_openai_http.supports_standalone_web_search=true",
                    ],
                )

            repo_home = repo / ".codex"
            repo_home.mkdir()
            (repo_home / "config.toml").write_text(
                'openai_base_url = "https://repo-controlled.invalid"\n',
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"CODEX_HOME": str(repo_home)}, clear=True
            ):
                self.assertEqual(AUTOREVIEW.codex_auth_config_flags(repo), [])

    def test_run_codex_base_url_preserves_auth_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo = root / "repo"
            repo.mkdir()
            temp_root = root / "tmp"
            temp_root.mkdir()
            fake_bin = root / "bin" / "codex"
            fake_bin.parent.mkdir(parents=True)
            fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_bin.chmod(0o755)

            for label, config_toml, with_auth_json, expect_linked, expect_keyring in (
                (
                    "file-auth",
                    'openai_base_url = "http://localhost:1337/v1"\n',
                    True,
                    True,
                    False,
                ),
                (
                    "keyring-auth",
                    (
                        'openai_base_url = "http://localhost:1337/v1"\n'
                        'cli_auth_credentials_store = "keyring"\n'
                    ),
                    False,
                    False,
                    True,
                ),
            ):
                with self.subTest(label):
                    external_home = root / f"host-{label}" / ".codex"
                    external_home.mkdir(parents=True)
                    (external_home / "config.toml").write_text(
                        config_toml, encoding="utf-8"
                    )
                    if with_auth_json:
                        (external_home / "auth.json").write_text(
                            '{"token":"test"}\n', encoding="utf-8"
                        )

                    captured: dict[str, object] = {}

                    def fake_run(cmd, cwd, **kwargs):
                        captured["cmd"] = list(cmd)
                        captured["env"] = dict(kwargs["env"])
                        captured["stream_display"] = kwargs.get("stream_display")
                        codex_home = Path(kwargs["env"]["CODEX_HOME"])
                        captured["auth_json_present"] = (codex_home / "auth.json").is_file()
                        output_idx = cmd.index("--output-last-message") + 1
                        Path(cmd[output_idx]).write_text(
                            json.dumps({"verdict": "clean", "findings": []}),
                            encoding="utf-8",
                        )
                        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

                    args = self.reviewer_for(
                        "--codex-bin", str(fake_bin), "--stream-engine-output"
                    )
                    with (
                        mock.patch.dict(
                            os.environ, {"CODEX_HOME": str(external_home)}, clear=True
                        ),
                        mock.patch.object(
                            AUTOREVIEW, "ensure_codex_isolation_supported", return_value=str(fake_bin)
                        ),
                        mock.patch.object(
                            AUTOREVIEW, "safe_temp_root", return_value=temp_root
                        ),
                        mock.patch.object(
                            AUTOREVIEW, "run_with_heartbeat", side_effect=fake_run
                        ),
                    ):
                        AUTOREVIEW.run_codex(args, repo, "review prompt")

                    codex_home = Path(captured["env"]["CODEX_HOME"])
                    self.assertNotEqual(codex_home.name, "provider-home")
                    self.assertEqual(captured["auth_json_present"], expect_linked)
                    self.assertFalse(captured["stream_display"].suppress_diagnostics)
                    cmd = captured["cmd"]
                    if expect_keyring:
                        self.assertIn('cli_auth_credentials_store="keyring"', cmd)
                        self.assertNotIn('cli_auth_credentials_store="file"', cmd)
                        self.assertEqual(codex_home, external_home.resolve())
                    else:
                        self.assertEqual(codex_home.name, "codex-home")
                        self.assertIn('cli_auth_credentials_store="file"', cmd)

    def test_codex_route_refuses_top_level_openai_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            repo = root / "repo"
            repo.mkdir()
            external_home = root / "host" / ".codex"
            external_home.mkdir(parents=True)
            (external_home / "config.toml").write_text(
                (
                    'openai_base_url = "http://localhost:1337/v1"\n'
                    "\n"
                    "[model_providers.gateway]\n"
                    'base_url = "https://api.example.com/v1"\n'
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.dict(
                    os.environ, {"CODEX_HOME": str(external_home)}, clear=True
                ),
                mock.patch.object(
                    AUTOREVIEW, "validate_codex_route_config", return_value=None
                ),
                self.assertRaises(SystemExit),
            ):
                AUTOREVIEW.load_codex_inference_route(
                    repo, (), hostname="api.example.com"
                )


if __name__ == "__main__":
    unittest.main()
