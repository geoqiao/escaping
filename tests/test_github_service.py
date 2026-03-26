from unittest.mock import MagicMock, patch
import pytest
from github_blog.services.github_service import GitHubService

def test_github_service_login_new_auth():
    with patch("github_blog.services.github_service.Github") as mock_github:
        with patch("github_blog.services.github_service.Auth") as mock_auth:
            # Mock the presence of Auth.Token (modern PyGithub)
            mock_auth.Token = MagicMock()
            
            GitHubService("fake-token")
            
            mock_auth.Token.assert_called_once_with("fake-token")
            mock_github.assert_called_once()

def test_github_service_login_old_auth():
    with patch("github_blog.services.github_service.Github") as mock_github:
        with patch("github_blog.services.github_service.Auth", spec=[]) as mock_auth:
            # Mock the absence of Auth.Token (older PyGithub)
            GitHubService("fake-token")
            
            mock_github.assert_called_once_with("fake-token")

@patch("github_blog.services.github_service.Github")
def test_github_service_get_repo(mock_github_class):
    mock_github_instance = mock_github_class.return_value
    service = GitHubService("fake-token")
    
    service.get_repo("user/repo")
    
    mock_github_instance.get_repo.assert_called_once_with("user/repo")

@patch("github_blog.services.github_service.Github")
def test_github_service_get_user_issues(mock_github_class):
    mock_github_instance = mock_github_class.return_value
    mock_github_instance.get_user.return_value.login = "me"
    
    service = GitHubService("fake-token")
    mock_repo = MagicMock()
    
    service.get_user_issues(mock_repo)
    
    mock_repo.get_issues.assert_called_once_with(creator="me")
