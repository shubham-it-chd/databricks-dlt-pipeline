import os
from atlassian import Confluence, Jira
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Atlassian configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

def connect_to_jira():
    """Connect to Jira and return a Jira client instance."""
    try:
        jira = Jira(
            url=JIRA_URL,
            username=JIRA_USERNAME,
            password=JIRA_API_TOKEN,
            cloud=True  # Set to False for Server/Data Center
        )
        return jira
    except Exception as e:
        print(f"Failed to connect to Jira: {e}")
        return None

def connect_to_confluence():
    """Connect to Confluence and return a Confluence client instance."""
    try:
        confluence = Confluence(
            url=CONFLUENCE_URL,
            username=CONFLUENCE_USERNAME,
            password=CONFLUENCE_API_TOKEN,
            cloud=True  # Set to False for Server/Data Center
        )
        return confluence
    except Exception as e:
        print(f"Failed to connect to Confluence: {e}")
        return None

def fetch_jira_issues(jira, project_key):
    """Fetch and display issues from a Jira project."""
    try:
        issues = jira.jql(f"project = {project_key} ORDER BY created DESC")["issues"]
        print(f"\nFound {len(issues)} issues in project {project_key}:")
        for issue in issues[:5]:  # Limit to 5 for brevity
            print(f"- {issue['key']}: {issue['fields']['summary']}")
    except Exception as e:
        print(f"Error fetching Jira issues: {e}")

def fetch_confluence_page(confluence, page_id):
    """Fetch and display a Confluence page by ID."""
    try:
        page = confluence.get_page_by_id(page_id, expand="body.view")
        print(f"\nConfluence Page: {page['title']}")
        print(f"URL: {CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}")
        print(f"Excerpt: {page['body']['view']['value'][:100]}...")  # Truncated for brevity
    except Exception as e:
        print(f"Error fetching Confluence page: {e}")

def main():
    """Main function to demonstrate Atlassian MCP integration."""
    print("Starting Atlassian MCP Sample Application...")
    
    # Connect to Jira and Confluence
    jira = connect_to_jira()
    confluence = connect_to_confluence()
    
    if jira:
        # Replace 'PROJ' with your Jira project key
        fetch_jira_issues(jira, "PROJ")
    else:
        print("Skipping Jira operations due to connection failure.")
    
    if confluence:
        # Replace '123456' with a valid Confluence page ID
        fetch_confluence_page(confluence, "123456")
    else:
        print("Skipping Confluence operations due to connection failure.")

if __name__ == "__main__":
    main()