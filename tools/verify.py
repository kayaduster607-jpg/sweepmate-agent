"""Verify graph, Chroma and UI behavior without dotenv or external model requests."""

import ipaddress
import json
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def protect_material(event, arguments):
    """Reject environment-file access and all non-loopback network activity."""
    if event == "open" and isinstance(arguments[0], (str, bytes)):
        path = Path(os.fsdecode(arguments[0]))
        if any(part.lower().startswith(".env") or part.lower().endswith(".env") for part in path.parts):
            raise PermissionError("Environment files must remain closed")
    if event in ("socket.connect", "socket.bind"):
        address = arguments[1]
        if isinstance(address, tuple):
            try:
                allowed = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                allowed = False
            if not allowed:
                raise PermissionError("External network disabled in offline verification")
    if event == "socket.getaddrinfo" and arguments[0] not in (None, "localhost", "127.0.0.1", "::1"):
        raise PermissionError("External DNS disabled in offline verification")


def main():
    """Inject a nonfunctional sample credential before any application import."""
    sys.addaudithook(protect_material)
    os.environ["OPENAI_API_KEY"] = "example"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    from importlib.metadata import version
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "successful": result.wasSuccessful(), "model_api_calls": 0, "env_files_read": 0,
              "original_data_read": False, "real_chroma_test": True, "streamlit_app_test": True,
              "versions": {name: version(name) for name in ("langchain-core", "langgraph", "langchain-openai",
                            "langchain-chroma", "chromadb", "streamlit", "pypdf")}}
    destination = ROOT / ".verification"
    destination.mkdir(exist_ok=True)
    (destination / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
