import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


class GitHubServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class GitHubService:
    def __init__(self, repository_url: str, provider: str, token: Optional[str] = None):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "").strip()
        if not self.token:
            raise GitHubServiceError(503, "GitHub token is not configured on the server")

        parsed = urlparse(repository_url)
        self.api_base_url = (
            "https://api.github.com"
            if provider == "github_cloud"
            else f"{parsed.scheme}://{parsed.netloc}/api/v3"
        )
        try:
            self.timeout = float(os.getenv("GITHUB_API_TIMEOUT_SECONDS", "20"))
        except ValueError as exc:
            raise GitHubServiceError(500, "GITHUB_API_TIMEOUT_SECONDS must be a number") from exc
        if self.timeout <= 0:
            raise GitHubServiceError(500, "GITHUB_API_TIMEOUT_SECONDS must be greater than zero")

    def _request(
        self,
        path: str,
        *,
        accept: str = "application/vnd.github+json",
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        try:
            response = requests.get(
                f"{self.api_base_url}{path}",
                headers={
                    "Accept": accept,
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params=params,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise GitHubServiceError(503, "GitHub API request timed out") from exc
        except requests.exceptions.RequestException as exc:
            raise GitHubServiceError(503, "Unable to connect to the GitHub API") from exc

        if response.status_code == 401:
            raise GitHubServiceError(401, "GitHub rejected the configured token")
        if response.status_code == 403:
            if response.headers.get("X-RateLimit-Remaining") == "0" or response.headers.get("Retry-After"):
                raise GitHubServiceError(429, "GitHub API rate limit exceeded")
            raise GitHubServiceError(403, "GitHub denied access to the requested resource")
        if response.status_code == 404:
            raise GitHubServiceError(404, "GitHub repository or pull request was not found")
        if response.status_code == 429:
            raise GitHubServiceError(429, "GitHub API rate limit exceeded")
        if not response.ok:
            raise GitHubServiceError(502, f"GitHub API returned HTTP {response.status_code}")
        return response

    def check_connection(self) -> Dict[str, str]:
        response = self._request("/user")
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubServiceError(502, "GitHub returned an invalid user response") from exc
        login = data.get("login") if isinstance(data, dict) else None
        if not isinstance(login, str) or not login:
            raise GitHubServiceError(502, "GitHub user response did not contain a login")
        return {"login": login}

    def fetch_pull_request(self, owner: str, repository: str, pr_number: int) -> Dict[str, Any]:
        response = self._request(f"/repos/{owner}/{repository}/pulls/{pr_number}")
        data = self._json_response(response, "pull request")
        if not isinstance(data, dict):
            raise GitHubServiceError(502, "GitHub returned an invalid pull request response")
        return data

    def fetch_commits(self, owner: str, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        return self._fetch_paginated(f"/repos/{owner}/{repository}/pulls/{pr_number}/commits", "commits")

    def fetch_changed_files(self, owner: str, repository: str, pr_number: int) -> List[Dict[str, Any]]:
        return self._fetch_paginated(f"/repos/{owner}/{repository}/pulls/{pr_number}/files", "changed files")

    def fetch_diff(self, owner: str, repository: str, pr_number: int) -> str:
        response = self._request(
            f"/repos/{owner}/{repository}/pulls/{pr_number}",
            accept="application/vnd.github.diff",
        )
        return response.text

    def _fetch_paginated(self, path: str, resource_name: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            response = self._request(path, params={"per_page": 100, "page": page})
            data = self._json_response(response, resource_name)
            if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
                raise GitHubServiceError(502, f"GitHub returned an invalid {resource_name} response")
            results.extend(data)
            if len(data) < 100:
                return results
            page += 1

    @staticmethod
    def _json_response(response: requests.Response, resource_name: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubServiceError(502, f"GitHub returned invalid JSON for {resource_name}") from exc
