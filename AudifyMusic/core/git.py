import asyncio
import shlex
from typing import Tuple
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
import config
from ..logging import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(install_requirements())


def git():
    REPO_LINK = config.UPSTREAM_REPO

    if config.GIT_TOKEN:
        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
        TEMP_REPO = REPO_LINK.split("https://")[1]
        UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
    else:
        UPSTREAM_REPO = REPO_LINK

    try:
        repo = Repo()
        LOGGER(__name__).info("Git Client Found [VPS DEPLOYER]")
    except (InvalidGitRepositoryError, GitCommandError):
        LOGGER(__name__).info("Not a Git repository. Initializing one...")
        repo = Repo.init()

        try:
            origin = repo.create_remote("origin", UPSTREAM_REPO)
        except Exception:
            origin = repo.remote("origin")

        try:
            origin.fetch()
        except Exception as e:
            LOGGER(__name__).warning(f"Failed to fetch from origin: {e}")
            return

        # Safely check if remote branch exists
        remote_branch = f"origin/{config.UPSTREAM_BRANCH}"
        if remote_branch in [ref.name for ref in origin.refs]:
            try:
                repo.create_head(config.UPSTREAM_BRANCH, origin.refs[config.UPSTREAM_BRANCH])
                repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(origin.refs[config.UPSTREAM_BRANCH])
                repo.heads[config.UPSTREAM_BRANCH].checkout(True)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to set up local branch: {e}")
        else:
            LOGGER(__name__).warning(f"Branch '{remote_branch}' not found in origin.")

        try:
            origin.fetch(config.UPSTREAM_BRANCH)
            origin.pull(config.UPSTREAM_BRANCH)
        except GitCommandError:
            repo.git.reset("--hard", "FETCH_HEAD")

        install_req("pip3 install --no-cache-dir -r requirements.txt")
        LOGGER(__name__).info("Fetched updates from upstream repository.")
