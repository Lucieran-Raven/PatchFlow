"""PR Automation Service for creating GitHub pull requests with security fixes.

This service handles:
1. Creating branches for fixes
2. Committing fix code
3. Opening pull requests
4. Tracking PR status
"""
import base64
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog
import httpx

from core.config import settings
from core.database import async_session_maker
from sqlalchemy import select
from models import Vulnerability, Repository, User

logger = structlog.get_logger()


class PRAutomationService:
    """Service for automating PR creation with security fixes."""
    
    def __init__(self):
        self.github_api_base = "https://api.github.com"
    
    async def create_fix_pr(
        self,
        vulnerability_id: str,
        user_id: str,
        custom_branch_name: Optional[str] = None,
        custom_pr_title: Optional[str] = None,
        custom_pr_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a pull request with the security fix for a vulnerability.
        
        Returns:
            Dict with pr_url, pr_number, branch_name, commit_sha, status
        """
        async with async_session_maker() as session:
            # Get vulnerability with repository and user
            result = await session.execute(
                select(Vulnerability, Repository, User)
                .join(Repository, Vulnerability.repository_id == Repository.id)
                .join(User, Repository.owner_id == User.id)
                .where(Vulnerability.id == vulnerability_id)
            )
            row = result.one_or_none()
            
            if not row:
                return {
                    "success": False,
                    "error": "Vulnerability not found",
                    "vulnerability_id": vulnerability_id
                }
            
            vuln, repo, user = row
            
            # Check if fix exists
            if not vuln.fix_generated or not vuln.fix_code:
                return {
                    "success": False,
                    "error": "No fix generated for this vulnerability. Generate fix first.",
                    "vulnerability_id": vulnerability_id
                }
            
            # Check if PR already exists
            if vuln.pr_url:
                return {
                    "success": False,
                    "error": f"PR already exists: {vuln.pr_url}",
                    "pr_url": vuln.pr_url,
                    "pr_number": vuln.pr_number
                }
            
            # Get GitHub token
            github_token = user.github_token
            if not github_token:
                return {
                    "success": False,
                    "error": "User has no GitHub token. Please reconnect GitHub account."
                }
            
            try:
                # Create PR using GitHub API
                pr_result = await self._create_github_pr(
                    github_token=github_token,
                    repo_full_name=repo.full_name,
                    default_branch=repo.default_branch or "main",
                    vuln=vuln,
                    fix_code=vuln.fix_code,
                    file_path=vuln.file_path,
                    custom_branch_name=custom_branch_name,
                    custom_pr_title=custom_pr_title,
                    custom_pr_body=custom_pr_body
                )
                
                if pr_result["success"]:
                    # Update vulnerability with PR info
                    vuln.pr_url = pr_result["pr_url"]
                    vuln.pr_number = pr_result["pr_number"]
                    vuln.status = "pr_created"
                    await session.commit()
                    
                    logger.info(
                        "PR created successfully",
                        vulnerability_id=vulnerability_id,
                        pr_number=pr_result["pr_number"],
                        pr_url=pr_result["pr_url"]
                    )
                
                return pr_result
                
            except Exception as e:
                logger.error(
                    "Failed to create PR",
                    vulnerability_id=vulnerability_id,
                    error=str(e)
                )
                return {
                    "success": False,
                    "error": f"Failed to create PR: {str(e)}",
                    "vulnerability_id": vulnerability_id
                }
    
    async def _create_github_pr(
        self,
        github_token: str,
        repo_full_name: str,
        default_branch: str,
        vuln: Vulnerability,
        fix_code: str,
        file_path: Optional[str],
        custom_branch_name: Optional[str] = None,
        custom_pr_title: Optional[str] = None,
        custom_pr_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Internal method to create PR via GitHub API."""
        
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # Generate branch name
        branch_name = custom_branch_name or self._generate_branch_name(vuln)
        
        # Generate PR title and body
        pr_title = custom_pr_title or self._generate_pr_title(vuln)
        pr_body = custom_pr_body or self._generate_pr_body(vuln, fix_code)
        
        async with httpx.AsyncClient() as client:
            # Step 1: Get the SHA of the default branch (for creating new branch)
            ref_url = f"{self.github_api_base}/repos/{repo_full_name}/git/ref/heads/{default_branch}"
            ref_response = await client.get(ref_url, headers=headers)
            
            if ref_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get default branch ref: {ref_response.text}"
                }
            
            base_sha = ref_response.json()["object"]["sha"]
            
            # Step 2: Create new branch
            create_branch_url = f"{self.github_api_base}/repos/{repo_full_name}/git/refs"
            branch_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            branch_response = await client.post(
                create_branch_url,
                headers=headers,
                json=branch_data
            )
            
            if branch_response.status_code not in [201, 422]:  # 422 means branch already exists
                return {
                    "success": False,
                    "error": f"Failed to create branch: {branch_response.text}"
                }
            
            # If branch already exists, we'll continue with it
            logger.info("Branch created or already exists", branch_name=branch_name)
            
            # Step 3: Get current file content (if file exists) to update it
            # For dependency upgrades, we need to modify the requirements/package file
            # For code changes, we modify the vulnerable file
            
            commit_sha = None
            
            if vuln.package_name:
                # Dependency upgrade - update package file
                commit_sha = await self._commit_dependency_upgrade(
                    client, headers, repo_full_name, branch_name, vuln, fix_code
                )
            elif file_path:
                # Code fix - modify the vulnerable file
                commit_sha = await self._commit_code_fix(
                    client, headers, repo_full_name, branch_name, file_path, vuln, fix_code
                )
            else:
                # No specific file - create a patch file or documentation
                commit_sha = await self._commit_patch_file(
                    client, headers, repo_full_name, branch_name, vuln, fix_code
                )
            
            if not commit_sha:
                return {
                    "success": False,
                    "error": "Failed to commit fix to branch"
                }
            
            # Step 4: Create pull request
            pr_url = f"{self.github_api_base}/repos/{repo_full_name}/pulls"
            pr_data = {
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": default_branch
            }
            
            pr_response = await client.post(pr_url, headers=headers, json=pr_data)
            
            if pr_response.status_code != 201:
                return {
                    "success": False,
                    "error": f"Failed to create pull request: {pr_response.text}"
                }
            
            pr_data = pr_response.json()
            
            return {
                "success": True,
                "pr_url": pr_data["html_url"],
                "pr_number": pr_data["number"],
                "branch_name": branch_name,
                "commit_sha": commit_sha,
                "title": pr_title,
                "body": pr_body
            }
    
    async def _commit_dependency_upgrade(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        repo_full_name: str,
        branch_name: str,
        vuln: Vulnerability,
        fix_code: str
    ) -> Optional[str]:
        """Commit dependency upgrade to requirements/package file."""
        
        # Detect file type based on repo language
        file_mapping = {
            "python": ["requirements.txt", "pyproject.toml", "setup.py"],
            "javascript": ["package.json"],
            "typescript": ["package.json"],
            "java": ["pom.xml", "build.gradle"],
            "go": ["go.mod"],
            "rust": ["Cargo.toml"],
            "ruby": ["Gemfile"],
        }
        
        # Try to find and update the appropriate file
        detected_files = file_mapping.get(vuln.repository.language.lower(), ["requirements.txt"])
        
        for filename in detected_files:
            file_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{filename}?ref={branch_name}"
            file_response = await client.get(file_url, headers=headers)
            
            if file_response.status_code == 200:
                file_data = file_response.json()
                current_content = base64.b64decode(file_data["content"]).decode("utf-8")
                
                # Generate new content based on file type
                new_content = self._update_dependency_file(
                    current_content, filename, vuln.package_name, 
                    vuln.current_version, vuln.fixed_version
                )
                
                if new_content:
                    # Commit the change
                    commit_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{filename}"
                    commit_data = {
                        "message": f"Security: Upgrade {vuln.package_name} to fix {vuln.cve_id or 'vulnerability'}",
                        "content": base64.b64encode(new_content.encode()).decode(),
                        "sha": file_data["sha"],
                        "branch": branch_name
                    }
                    
                    commit_response = await client.put(commit_url, headers=headers, json=commit_data)
                    
                    if commit_response.status_code in [200, 201]:
                        return commit_response.json()["commit"]["sha"]
        
        return None
    
    async def _commit_code_fix(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        repo_full_name: str,
        branch_name: str,
        file_path: str,
        vuln: Vulnerability,
        fix_code: str
    ) -> Optional[str]:
        """Commit code fix to the vulnerable file."""
        
        file_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{file_path}?ref={branch_name}"
        file_response = await client.get(file_url, headers=headers)
        
        if file_response.status_code != 200:
            # File doesn't exist, create new file with fix
            commit_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{file_path}"
            commit_data = {
                "message": f"Security fix: {vuln.cwe_id or 'Vulnerability'}",
                "content": base64.b64encode(fix_code.encode()).decode(),
                "branch": branch_name
            }
            
            commit_response = await client.put(commit_url, headers=headers, json=commit_data)
            if commit_response.status_code in [200, 201]:
                return commit_response.json()["commit"]["sha"]
            return None
        
        # File exists, update it
        file_data = file_response.json()
        
        # For now, replace entire file with patched code
        # In a more advanced version, we'd apply a proper diff
        commit_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{file_path}"
        commit_data = {
            "message": f"Security fix: {vuln.cwe_id or 'Vulnerability'} - {vuln.title[:50]}",
            "content": base64.b64encode(fix_code.encode()).decode(),
            "sha": file_data["sha"],
            "branch": branch_name
        }
        
        commit_response = await client.put(commit_url, headers=headers, json=commit_data)
        
        if commit_response.status_code in [200, 201]:
            return commit_response.json()["commit"]["sha"]
        
        return None
    
    async def _commit_patch_file(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        repo_full_name: str,
        branch_name: str,
        vuln: Vulnerability,
        fix_code: str
    ) -> Optional[str]:
        """Create a patch file with the fix."""
        
        patch_filename = f"security-patches/{vuln.cve_id or vuln.cwe_id or 'fix'}-{vuln.id[:8]}.patch"
        patch_content = f"""# Security Fix Patch
# Vulnerability: {vuln.title}
# CVE: {vuln.cve_id or 'N/A'}
# CWE: {vuln.cwe_id or 'N/A'}
# Severity: {vuln.severity}

## Fix Instructions

{fix_code}

## Test Cases

{vuln.test_cases or 'No test cases generated'}

---
Generated by PatchFlow Security Platform
"""
        
        commit_url = f"{self.github_api_base}/repos/{repo_full_name}/contents/{patch_filename}"
        commit_data = {
            "message": f"Security patch: {vuln.cve_id or vuln.cwe_id or 'Vulnerability'}",
            "content": base64.b64encode(patch_content.encode()).decode(),
            "branch": branch_name
        }
        
        commit_response = await client.put(commit_url, headers=headers, json=commit_data)
        
        if commit_response.status_code in [200, 201]:
            return commit_response.json()["commit"]["sha"]
        
        return None
    
    def _update_dependency_file(
        self,
        current_content: str,
        filename: str,
        package_name: str,
        current_version: Optional[str],
        fixed_version: Optional[str]
    ) -> Optional[str]:
        """Update dependency file with new version."""
        
        if not fixed_version:
            return None
        
        if filename == "requirements.txt":
            # Update requirements.txt
            lines = current_content.split("\n")
            new_lines = []
            for line in lines:
                if package_name.lower() in line.lower() and not line.strip().startswith("#"):
                    # Replace version
                    new_line = f"{package_name}>={fixed_version}"
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            return "\n".join(new_lines)
        
        elif filename == "package.json":
            # Update package.json - would need proper JSON parsing
            # For now, simple string replacement
            if current_version:
                old_pattern = f'"{package_name}": "{current_version}"'
                new_pattern = f'"{package_name}": "^{fixed_version}"'
                return current_content.replace(old_pattern, new_pattern)
        
        # Default: return as-is for other formats
        return current_content
    
    def _generate_branch_name(self, vuln: Vulnerability) -> str:
        """Generate a unique branch name for the fix."""
        prefix = "security-fix"
        
        if vuln.cve_id:
            identifier = vuln.cve_id.replace("CVE-", "cve-")
        elif vuln.cwe_id:
            identifier = vuln.cwe_id.replace("CWE-", "cwe-")
        elif vuln.package_name:
            identifier = vuln.package_name.replace(" ", "-").lower()
        else:
            identifier = f"vuln-{vuln.id[:8]}"
        
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        return f"{prefix}/{identifier}-{timestamp}"
    
    def _generate_pr_title(self, vuln: Vulnerability) -> str:
        """Generate PR title."""
        if vuln.cve_id:
            return f"Security: Fix {vuln.cve_id} - {vuln.title[:50]}"
        elif vuln.cwe_id:
            return f"Security: Fix {vuln.cwe_id} - {vuln.title[:50]}"
        else:
            return f"Security: Fix {vuln.title[:60]}"
    
    def _generate_pr_body(self, vuln: Vulnerability, fix_code: str) -> str:
        """Generate PR description."""
        body = f"""## 🔒 Security Fix

### Vulnerability Details
- **Title:** {vuln.title}
- **CVE ID:** {vuln.cve_id or 'N/A'}
- **CWE ID:** {vuln.cwe_id or 'N/A'}
- **Severity:** {vuln.severity}
- **File:** {vuln.file_path or 'N/A'}

### Description
{vuln.description or 'No description available'}

### Fix Applied
```
{fix_code[:500]}{'...' if len(fix_code) > 500 else ''}
```

### Test Cases
{vuln.test_cases or 'No test cases generated'}

---
🤖 **Generated by [PatchFlow](https://patchflow.io) - Autonomous AI Security Remediation**
"""
        return body
    
    async def get_pr_status(
        self,
        vulnerability_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Get the current status of a PR."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Vulnerability, Repository, User)
                .join(Repository, Vulnerability.repository_id == Repository.id)
                .join(User, Repository.owner_id == User.id)
                .where(Vulnerability.id == vulnerability_id)
            )
            row = result.one_or_none()
            
            if not row:
                return {"error": "Vulnerability not found"}
            
            vuln, repo, user = row
            
            if not vuln.pr_number:
                return {
                    "status": "no_pr",
                    "message": "No PR has been created for this vulnerability"
                }
            
            # Fetch PR status from GitHub
            headers = {
                "Authorization": f"token {user.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with httpx.AsyncClient() as client:
                pr_url = f"{self.github_api_base}/repos/{repo.full_name}/pulls/{vuln.pr_number}"
                pr_response = await client.get(pr_url, headers=headers)
                
                if pr_response.status_code != 200:
                    return {
                        "status": "unknown",
                        "pr_url": vuln.pr_url,
                        "pr_number": vuln.pr_number,
                        "error": "Failed to fetch PR status"
                    }
                
                pr_data = pr_response.json()
                
                return {
                    "status": pr_data["state"],  # open, closed
                    "merged": pr_data.get("merged", False),
                    "mergeable": pr_data.get("mergeable"),
                    "pr_url": vuln.pr_url,
                    "pr_number": vuln.pr_number,
                    "title": pr_data["title"],
                    "created_at": pr_data["created_at"],
                    "updated_at": pr_data["updated_at"],
                    "draft": pr_data["draft"],
                    "checks_passing": None  # Would need to fetch check runs
                }


# Global service instance
pr_service = PRAutomationService()
