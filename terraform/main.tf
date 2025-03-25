terraform {
  required_version = ">= 1.0.0"
  
  backend "remote" {
    organization = "Patricia7sp"
    
    workspaces {
      name = "youtube-automation"
    }
  }
}

provider "github" {
  token = var.github_token
}

resource "github_repository" "automation" {
  name        = "youtube-automation"
  description = "Repositório para automação de vídeos do YouTube"
  private     = true
  
  topics = [
    "youtube",
    "automation",
    "ci-cd",
    "terraform"
  ]
}

resource "github_repository_webhook" "ci_cd" {
  repository = github_repository.automation.name
  
  configuration {
    url          = "https://api.github.com/repos/${github_repository.automation.name}/dispatches"
    content_type = "json"
    insecure_ssl = true
    
    events = [
      "push",
      "pull_request",
      "workflow_run"
    ]
  }
  
  active = true
}
