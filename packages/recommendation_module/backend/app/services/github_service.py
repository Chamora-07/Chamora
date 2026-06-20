import requests
from urllib.parse import urlparse
from ..core.config import settings


def _github_headers():
    headers = {
        "Accept": "application/vnd.github+json"
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


def _parse_repo(repo_url: str):
    """
    Converts:
    https://github.com/ranathungaWK/Testing-Environment-
    into:
    owner=ranathungaWK, repo=Testing-Environment-
    """
    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repo URL")
    return parts[0], parts[1]


def _get_repo_contents(owner: str, repo: str, path: str = ""):
    url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, headers=_github_headers(), timeout=10)
    response.raise_for_status()
    return response.json()


def _safe_fetch_contents(owner: str, repo: str, path: str):
    try:
        return _get_repo_contents(owner, repo, path)
    except Exception:
        return []


def extract_tech_stack(repo_url: str) -> dict:
    """
    Rule-based extraction for demo.
    Checks root and common folders for package.json, requirements.txt, pom.xml, Dockerfile, etc.
    """
    try:
        owner, repo = _parse_repo(repo_url)

        root_items = _safe_fetch_contents(owner, repo, "")
        frontend_items = _safe_fetch_contents(owner, repo, "frontend")
        backend_items = _safe_fetch_contents(owner, repo, "backend")

        root_names = {item["name"] for item in root_items} if isinstance(root_items, list) else set()
        frontend_names = {item["name"] for item in frontend_items} if isinstance(frontend_items, list) else set()
        backend_names = {item["name"] for item in backend_items} if isinstance(backend_items, list) else set()

        evidence = []
        frontend = "Unknown"
        backend = "Unknown"
        database = "Unknown"
        apis = []

        # Frontend inference
        if "package.json" in root_names or "package.json" in frontend_names:
            frontend = "React / JavaScript"
            evidence.append("package.json")

        if "src" in frontend_names:
            evidence.append("frontend/src structure")

        # Backend inference
        if "requirements.txt" in root_names or "requirements.txt" in backend_names:
            backend = "Python"
            evidence.append("requirements.txt")

        if "pom.xml" in root_names or "pom.xml" in backend_names:
            backend = "Java"
            evidence.append("pom.xml")

        if "package.json" in backend_names and backend == "Unknown":
            backend = "Node.js"
            evidence.append("backend/package.json")

        if "Dockerfile" in root_names:
            evidence.append("Dockerfile")

        # Very light database hinting
        # Later, this can inspect env files, compose files, docs, backend configs
        if "docker-compose.yml" in root_names or "docker-compose.yaml" in root_names:
            evidence.append("docker-compose")

        return {
            "frontend": frontend,
            "backend": backend if backend != "Unknown" else "Node.js",
            "database": database,
            "apis": apis,
            "evidence": evidence if evidence else ["repo scanned"]
        }

    except Exception:
        return {
            "frontend": "React / JavaScript",
            "backend": "Node.js",
            "database": "Unknown",
            "apis": [],
            "evidence": ["fallback inference"]
        }