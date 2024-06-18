import os
import requests

# GitHub API endpoint for repository contents
github_api_url = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

def extract_github_details(repo_url):
    # Example repo_url: https://github.com/username/repository-name/tree/branch/path
    parts = repo_url.rstrip('/').split('/')
    owner = parts[-3]
    repo = parts[-2]
    path = '/'.join(parts[5:]) if len(parts) > 5 else ''  # Extract path after '/tree/branch'

    return owner, repo, path

def fetch_directory_structure_from_github(owner, repo, path=''):
    url = github_api_url.format(owner=owner, repo=repo, path=path)
    response = requests.get(url)

    if response.status_code == 200:
        contents = response.json()

        structure = []
        for item in contents:
            if item['type'] == 'dir':
                structure.append(f"│   ├── {item['name']}/")
                structure.extend(fetch_directory_structure_from_github(owner, repo, item['path']))
            else:
                structure.append(f"│   ├── {item['name']}")

        return structure
    else:
        raise ValueError(f"Failed to fetch directory structure: {response.status_code} - {response.text}")

def write_directory_structure_to_file(structure, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write("\n".join(structure))

# Example usage
if __name__ == "__main__":
    # Prompt user for GitHub repository URL
    repo_url = input("Enter GitHub repository URL: ").strip()

    try:
        # Extract GitHub details from URL
        github_owner, github_repo, github_path = extract_github_details(repo_url)

        # Output file name
        output_file = f"{github_repo}_directory_structure.txt"

        # Fetch directory structure from GitHub
        structure = fetch_directory_structure_from_github(github_owner, github_repo, github_path)
        
        # Write directory structure to file
        write_directory_structure_to_file(structure, output_file)
        print(f"Directory structure written to {output_file}")
    
    except Exception as e:
        print(f"Error: {e}")
