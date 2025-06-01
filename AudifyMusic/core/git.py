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
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    import os

    REPO_LINK = config.UPSTREAM_REPO
    BRANCH = config.UPSTREAM_BRANCH

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

        # Fetch all branches
        try:
            origin.fetch()
        except GitCommandError as e:
            LOGGER(__name__).warning(f"Fetch failed: {e}")
            return

        # Verify the branch exists remotely
        remote_refs = [ref.name for ref in origin.refs]
        target_ref = f"origin/{BRANCH}"

        if target_ref in remote_refs:
            try:
                repo.create_head(BRANCH, origin.refs[BRANCH])
                repo.heads[BRANCH].set_tracking_branch(origin.refs[BRANCH])
                repo.heads[BRANCH].checkout()
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to set up tracking branch: {e}")

            try:
                origin.pull(BRANCH)
            except GitCommandError as e:
                LOGGER(__name__).warning(f"Pull failed: {e}")
                # Only reset if FETCH_HEAD exists
                fetch_head_path = os.path.join(repo.git_dir, "FETCH_HEAD")
                if os.path.exists(fetch_head_path):
                    repo.git.reset("--hard", "FETCH_HEAD")
        else:
            LOGGER(__name__).warning(f"Remote branch '{target_ref}' does not exist.")

        install_req("pip3 install --no-cache-dir -r requirements.txt")
        LOGGER(__name__).info("Finished Git setup.")
