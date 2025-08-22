# GitGuardian Pre-Commit Installation Guide

This guide outlines the steps to set up GitGuardian's `ggshield` CLI tool with the pre-commit framework to detect secrets in your Git commits.

## Prerequisites

- Python 3.8 or newer installed.
- Git installed on your system.
- A GitGuardian workspace account.
- The `pre-commit` framework installed in your repository. Install it using:

  ```bash
  pip install pre-commit
  ```

## Step-by-Step Installation

1. **Install ggshield**

   Install the `ggshield` CLI tool using pip (preferably in a virtual environment to avoid conflicts):

   ```bash
   pip install ggshield
   ```

   Alternatively, use Homebrew on macOS:

   ```bash
   brew install gitguardian/tap/ggshield
   ```

   Note: Avoid installing via pip on systems where Python is externally managed (e.g., Debian 12). Use standalone packages from the ggshield release page if needed.

2. **Authenticate with GitGuardian**

   - Sign in to your GitGuardian workspace and create a Personal Access Token (PAT) from your personal settings.
   - Set the PAT as an environment variable:

     ```bash
     export GITGUARDIAN_API_KEY="your_personal_access_token"
     ```

     Alternatively, use the `ggshield auth login` command to automate PAT provisioning:

     ```bash
     ggshield auth login
     ```

     This opens a browser window to log in and configure the token.

3. **Configure the Pre-Commit Hook**

   - Create or update a `.pre-commit-config.yaml` file in the root of your repository.
   - Add the following configuration to include the `ggshield` hook:

     ```yaml
     repos:
       - repo: https://github.com/gitguardian/ggshield
         rev: v1.42.0
         hooks:
           - id: ggshield
             language_version: python3
             stages: [pre-commit]
     ```

     Note: Replace `v1.42.0` with the latest stable release from the GitGuardian GitHub repository. Using `main` may cause warnings or instability.

4. **Check Git Configuration for core.hooksPath**

   - Ensure the Git `core.hooksPath` is set to the default `.git/hooks` directory to avoid conflicts with custom hook paths. Run the following command to check the current setting:

     ```bash
     git config core.hooksPath
     ```

     - If the output is empty or set to `.git/hooks`, no changes are needed.
     - If it’s set to a custom path (e.g., due to tools like Husky), reset it to the default:

       ```bash
       git config --unset core.hooksPath
       ```

     - Verify the change by running `git config core.hooksPath` again. It should return nothing or `.git/hooks`. This ensures the pre-commit hooks run from the repository’s default hooks directory.

5. **Install the Pre-Commit Hook**

   - Run the following command to install the pre-commit hooks into your Git repository:

     ```bash
     pre-commit install
     ```

     This sets up the hooks to run automatically before each commit. If a `.git/hooks/pre-commit` file already exists, it won’t be overridden unless you use the `--force` option:

     ```bash
     pre-commit install --force
     ```

6. **Test the Hook**

   - To verify the hook works, try committing a file with a dummy secret (e.g., a test token from canarytokens.org). The hook should detect the secret and block the commit.
   - To bypass the hook for a specific commit (not recommended), use:

     ```bash
     git commit --no-verify
     ```

   - To manually run the hook on all files:

     ```bash
     pre-commit run --all-files
     ```

## Optional: Using ggshield with Docker

If you prefer using Docker, you can configure the pre-commit hook to run `ggshield` in a Docker container:

```yaml
repos:
  - repo: https://github.com/gitguardian/ggshield
    rev: v1.42.0
    hooks:
      - id: docker-ggshield
        language_version: docker_image
        stages: [pre-commit]
```

Run the scan with:

```bash
docker run -e GITGUARDIAN_API_KEY -v $(pwd):/data --rm gitguardian/ggshield:latest ggshield secret scan pre-commit
```

## Additional Notes

- **Skipping Checks**: To skip pre-commit checks for a specific commit, use the `-n` flag:

  ```bash
  git commit -n -m "Your commit message"
  ```

- **Custom Remediation Messages**: Customize remediation messages in the `.gitguardian.yaml` file to guide developers on resolving detected secrets. See GitGuardian CLI custom remediation message for details.

- **Ignoring Secrets**: To ignore specific secrets, use:

  ```bash
  ggshield secret ignore last-found
  ```

  This creates or updates a `.gitguardian.yaml` file to ignore the specified secret in future scans.

- **Performance**: The hook scans only staged files by default, ensuring minimal performance impact. For large repositories, test locally to avoid false positives or delays.

- **Limitations**: Pre-commit hooks are client-side and depend on developers installing them. They should complement server-side checks (e.g., pre-receive hooks) for comprehensive security.

## Troubleshooting

- If you encounter the error `GitGuardian API Key is needed`, ensure the `GITGUARDIAN_API_KEY` environment variable is set or use `ggshield auth login`.
- If hooks fail due to missing dependencies, install required system packages (e.g., `libyaml-dev` for YAML checks).
- If hooks fail to run, verify that `core.hooksPath` is unset or set to `.git/hooks` (see Step 4).
- For conflicts with other hooks (e.g., Husky), install Husky first, then `pre-commit`, as `pre-commit` can run existing hooks.