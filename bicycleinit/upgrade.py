import logging
import os
import subprocess


def upgrade(branch: str):
    old_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()

    try:
        subprocess.run(["git", "fetch", "origin", branch], check=True)
    except subprocess.CalledProcessError:
        logging.warning(f"Could not fetch updates from origin/{branch}. No update applied.")
        return False

    remote_hash = subprocess.check_output(["git", "rev-parse", f"origin/{branch}"]).strip()

    if old_hash == remote_hash:
        logging.info("Already up to date. No restart needed.")
        return False

    try:
        subprocess.run(["git", "pull", "--ff-only", "origin", branch], check=True)
        new_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()
        if old_hash != new_hash:
            logging.info("New version detected. Restarting...")
            return True
        else:
            logging.info(
                "No changes applied after pull - probably local changes present which might cause problems later"
            )
            return False
    except subprocess.CalledProcessError:
        logging.warning("Could not fast-forward. Merge conflicts detected. No update applied.")
    return False


def clone_or_pull_repo(git_url: str, repo_dir: str, branch: str = "main"):
    if not os.path.exists(repo_dir):
        logging.info(f"Cloning repository {git_url} into {repo_dir}")
        subprocess.run(["git", "clone", "--branch", branch, git_url, repo_dir], check=True)
    else:
        logging.info(f"Pulling latest changes for repository in {repo_dir}")
        try:
            subprocess.run(["git", "-C", repo_dir, "fetch", "origin", branch], check=True)
        except subprocess.CalledProcessError:
            logging.warning(f"Could not fetch updates from origin/{branch} for {repo_dir}. No update applied.")
            return
        try:
            subprocess.run(["git", "-C", repo_dir, "pull", "--ff-only", "origin", branch], check=True)
        except subprocess.CalledProcessError:
            logging.warning(f"Could not fast-forward in {repo_dir}. Performing hard reset to origin/{branch}.")
        # Always perform hard reset to ensure local changes are gone
        subprocess.run(["git", "-C", repo_dir, "reset", "--hard", f"origin/{branch}"], check=True)
