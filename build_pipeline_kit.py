"""Package the reusable framework with an explicit allowlist, never local data."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = [
    "poc.py", "api.py", "pipeline.py", "pipeline_spec.py", "pipeline_launch.py",
    "launch.py", "start.sh", "setup.sh", "Open PoC.command", "New Pipeline.command",
    "test_routing.py", "test_pipeline.py", "package.json", "package-lock.json",
    "PIPELINE.md", "ui/live.html", "ui/live.css", "ui/live.js", "build_pipeline_kit.py",
    "workflow.py", "workflow_launch.py", "Workflow Studio.command", "WORKFLOW-MVP.md",
    "reload_gateway.py", "test_reload_gateway.py",
    "test_workflow.py", "ui/workflow.html", "ui/workflow.css", "ui/workflow.js",
    "ui/workflow-view.css", "ui/workflow-view.js",
    "ui/workflow-templates.json", "ui/crew-entry.html", "ui/crew-entry.js",
    "workflow_library.py", "workflow_files.py", "requirements-workflow.txt",
    "test_workflow_library.py", "docs/DEVELOPMENT-HANDBOOK.md",
    "docs/OPERATIONS.md",
    "docs/FEATURES-AND-DECISIONS.md", "docs/RELEASE-NOTES.md",
    "examples/generated-review-workflow.yaml", "examples/generated-review-workflow.md",
    "workflows/development.json", "workflows/routing-proof.json",
    "README.md", "PLAN.md", "CONTRIBUTING.md", ".gitignore",
    "docs/BASELINE.md", "docs/SOURCES.md", "docs/THIRD-PARTY-NOTICES.md",
    "docs/PUBLICATION-VERIFICATION.md",
    "docs/experiments/EC2-001.md",
    "docs/architecture/ENTERPRISE.md", "docs/architecture/CONNECTORS.md",
    "docs/architecture/baseline/architecture.svg",
    "docs/architecture/baseline/interaction.svg",
    "docs/architecture/baseline/context.svg",
    "examples/ec2-four-agent-auto.yaml",
]


def main():
    destination = ROOT / "kirocrew-octopus-kit.zip"
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, "kirocrew-octopus/" + name)
        archive.writestr("kirocrew-octopus/package-manifest.json",
                         json.dumps({"files": hashes, "excludes": ["credentials", "user sessions", "backups", "node_modules", "local runs"]},
                                    ensure_ascii=False, indent=2))
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(FILES) + 1
    print(f"{destination} · {destination.stat().st_size} bytes")


if __name__ == "__main__":
    main()
