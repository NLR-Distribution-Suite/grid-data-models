from pathlib import Path
import subprocess
import platform
import sys

VERSION = "2.3.8"
SUPPORTED_VERSIONS = [VERSION]


def is_git_repo(dir: Path) -> bool:
    """Returns true if it is a git repo."""
    git_path = dir / ".git"
    return git_path.exists()


def has_git_installed() -> bool:
    """Returns true if git is installed."""
    try:
        subprocess.check_output(["git", "--help"])
        return True
    except subprocess.CalledProcessError:
        return False
    except OSError:
        return False


def get_git_commit(dir: Path) -> str:
    """Returns SHA-1 of HEAD of git repo."""
    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=dir)
        .decode("utf-8")
        .strip()
    )


def version_summary() -> str:
    """Returns complete version summary."""
    import importlib_metadata

    dependent_packages = ["networkx", "infrasys"]

    dep_pkg_versions = []
    for dist in importlib_metadata.distributions():
        name = dist.metadata.get("name")
        if name in dependent_packages:
            dep_pkg_versions.append(f"{name}-{dist.version}")

    gdm_dir = Path(__file__).parents[2]
    recent_commit = (
        get_git_commit(gdm_dir) if is_git_repo(gdm_dir) and has_git_installed() else "unknown"
    )

    summary = {
        "gdm version": VERSION,
        "dep_pkgs": " ".join(dep_pkg_versions),
        "platform": platform.platform(),
        "commit": recent_commit,
        "python_version": sys.version,
        "install_path": Path(__file__).resolve().parent,
    }
    return "\n".join(
        "{:>30} {}".format(k + ":", str(v).replace("\n", " ")) for k, v in summary.items()
    )
