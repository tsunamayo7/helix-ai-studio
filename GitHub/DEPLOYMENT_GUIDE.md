# GitHub Deployment Guide

This guide explains how to prepare and deploy Helix AI Studio to GitHub.

## Files in This Directory

The `GitHub/` directory contains all files needed for GitHub publication:

### Essential Files (Already Present)
- `README.md` - English documentation
- `README_ja.md` - Japanese documentation
- `LICENSE` - MIT License
- `.gitignore` - Git ignore rules
- `requirements.txt` - Python dependencies

### Community Standards (Newly Added)
- `CHANGELOG.md` - Version history
- `SECURITY.md` - Security policy and vulnerability reporting
- `CONTRIBUTING.md` - Contribution guidelines
- `.github/pull_request_template.md` - PR template
- `.github/ISSUE_TEMPLATE/bug_report.md` - Bug report template
- `.github/ISSUE_TEMPLATE/feature_request.md` - Feature request template
- `.github/ISSUE_TEMPLATE/config.yml` - Issue template config

### CI/CD (GitHub Actions)
- `.github/workflows/lint.yml` - Code linting workflow
- `.github/workflows/test.yml` - Test workflow
- `.github/workflows/build.yml` - Build workflow

### Documentation Assets
- `docs/screenshots/README.md` - Screenshot guidelines

## Pre-Deployment Checklist

### 1. Update Personal Information

Replace placeholders in the following files:

- [ ] `SECURITY.md`: Replace `[YOUR_SECURITY_EMAIL@example.com]` with actual contact
- [ ] All files: Replace `tomlo` with your GitHub username
- [ ] `README.md` and `README_ja.md`: Update installation command URLs

### 2. Add Screenshots

1. Take screenshots of the application
2. Save them to `docs/screenshots/` with descriptive names
3. Verify that the screenshot paths in README files match the actual filenames

### 3. Review and Customize

- [ ] Review `CONTRIBUTING.md` and adjust guidelines to your preferences
- [ ] Review `SECURITY.md` and set realistic response timelines
- [ ] Review `.gitignore` and ensure it matches your project structure
- [ ] Review GitHub Actions workflows and adjust as needed

### 4. Prepare Project Root

Copy files from `GitHub/` to your project root:

```bash
# Windows Command Prompt
cd "C:\Users\tomot\Desktop\開発環境\生�EAIアプリ\Helix AI Studio"

# Copy essential files
copy "GitHub\README.md" "README.md"
copy "GitHub\README_ja.md" "README_ja.md"
copy "GitHub\LICENSE" "LICENSE"
copy "GitHub\.gitignore" ".gitignore"
copy "GitHub\requirements.txt" "requirements.txt"
copy "GitHub\CHANGELOG.md" "CHANGELOG.md"
copy "GitHub\SECURITY.md" "SECURITY.md"
copy "GitHub\CONTRIBUTING.md" "CONTRIBUTING.md"

# Copy .github directory
xcopy "GitHub\.github" ".github" /E /I /H

# Copy docs directory
xcopy "GitHub\docs" "docs" /E /I
```

Or use PowerShell:

```powershell
# PowerShell
cd "C:\Users\tomot\Desktop\開発環境\生�EAIアプリ\Helix AI Studio"

# Copy files
Copy-Item "GitHub\README.md" -Destination "README.md"
Copy-Item "GitHub\README_ja.md" -Destination "README_ja.md"
Copy-Item "GitHub\LICENSE" -Destination "LICENSE"
Copy-Item "GitHub\.gitignore" -Destination ".gitignore"
Copy-Item "GitHub\requirements.txt" -Destination "requirements.txt"
Copy-Item "GitHub\CHANGELOG.md" -Destination "CHANGELOG.md"
Copy-Item "GitHub\SECURITY.md" -Destination "SECURITY.md"
Copy-Item "GitHub\CONTRIBUTING.md" -Destination "CONTRIBUTING.md"

# Copy directories
Copy-Item "GitHub\.github" -Destination ".github" -Recurse -Force
Copy-Item "GitHub\docs" -Destination "docs" -Recurse -Force
```

### 5. Initialize Git Repository

```bash
# Initialize repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Helix AI Studio v8.4.2"

# Add remote repository
git remote add origin https://github.com/tsunamayo7/helix-ai-studio.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### 6. Configure GitHub Repository Settings

After pushing:

1. **Enable Issues and Discussions**:
   - Go to Settings ↁEGeneral ↁEFeatures
   - Check "Issues" and "Discussions"

2. **Set Branch Protection Rules** (optional):
   - Go to Settings ↁEBranches
   - Add rule for `main` branch
   - Enable "Require pull request reviews before merging"

3. **Enable Security Features**:
   - Go to Settings ↁESecurity & analysis
   - Enable "Dependency graph"
   - Enable "Dependabot alerts"
   - Enable "Secret scanning"

4. **Add Topics**:
   - Go to repository main page
   - Click gear icon next to "About"
   - Add topics: `ai`, `llm`, `claude`, `ollama`, `pyqt6`, `desktop-app`, `orchestration`, `rag`, `windows`

5. **Configure Secrets** (for CI/CD, if needed):
   - Go to Settings ↁESecrets and variables ↁEActions
   - Add any necessary secrets (e.g., `ANTHROPIC_API_KEY` for tests)

## Post-Deployment

### Create First Release

1. Go to Releases ↁE"Create a new release"
2. Tag: `v8.4.2`
3. Title: `Helix AI Studio v8.4.2 "Contextual Intelligence"`
4. Description: Copy from CHANGELOG.md
5. Attach built executable (if available)
6. Publish release

### Community Health

After deployment, GitHub will show a "Community Profile" checklist:
- ✁EDescription
- ✁EREADME
- ✁ECode of conduct (optional, can add later)
- ✁EContributing guidelines
- ✁ELicense
- ✁EIssue templates
- ✁EPull request template

### Continuous Maintenance

- Monitor GitHub Actions for build/lint failures
- Respond to issues and PRs promptly
- Update CHANGELOG.md for each release
- Keep dependencies up to date

## Troubleshooting

### Common Issues

**Issue**: GitHub Actions fail on first run
**Solution**: Check workflow file syntax, ensure all referenced files exist

**Issue**: Screenshots don't display in README
**Solution**: Verify file paths are relative and files are committed

**Issue**: CI fails due to missing dependencies
**Solution**: Update `requirements.txt` with all necessary packages

## Support

For questions about deployment, open a discussion in your repository or contact maintainers.

---

**Ready to publish? Follow the checklist above and deploy with confidence!**
