# Contributing Guide

Thank you for your interest in contributing to the Adaptive RAG Clinical Assistant!

## 🌿 Branching Strategy

We use a simplified Git Flow model:

```
main                    # Production-ready code
├── develop             # Integration branch for features
│   ├── feature/*       # New features
│   ├── bugfix/*        # Bug fixes
│   └── experiment/*    # Experimental changes
└── release/*           # Release preparation
```

### Branch Naming Convention

| Branch Type | Pattern | Example |
|-------------|---------|---------|
| Feature | `feature/short-description` | `feature/multi-document-support` |
| Bug Fix | `bugfix/issue-description` | `bugfix/rrf-score-calculation` |
| Experiment | `experiment/hypothesis` | `experiment/cohere-embeddings` |
| Release | `release/vX.Y.Z` | `release/v1.1.0` |

### Workflow

1. **Start from develop**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**
   ```bash
   git add .
   git commit -m "feat: add multi-document support"
   ```

3. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create Pull Request to develop branch
   ```

4. **After review, merge to develop**

5. **Release process**
   ```bash
   git checkout -b release/v1.1.0 develop
   # Update version numbers, changelog
   git checkout main
   git merge release/v1.1.0
   git tag v1.1.0
   ```

## 📝 Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Build/tooling changes

**Examples:**
```
feat(retrieval): implement true RRF algorithm
fix(personas): correct executive detection logic
docs(readme): add architecture diagram
refactor(prompts): extract common formatting logic
```

## 🧪 Testing Guidelines

1. **Unit tests** for new functions in `tests/`
2. **Integration tests** for retrieval pipeline
3. Run tests before PR:
   ```bash
   pytest tests/ -v
   ```

## 📋 PR Checklist

- [ ] Code follows project style guidelines
- [ ] Self-reviewed the code
- [ ] Added/updated relevant documentation
- [ ] Added tests for new functionality
- [ ] All tests passing
- [ ] No new linting errors
- [ ] Updated CHANGELOG.md if applicable

## 🔧 Development Setup

```bash
# Clone repo
git clone https://github.com/Don-K-Quixote/Adaptive-RAG-Clinical-Assistant.git
cd Adaptive-RAG-Clinical-Assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest black flake8

# Create .env file
cp .env.example .env
# Edit .env with your API keys
```

## 💡 Feature Ideas

Looking for something to work on? Consider:

1. **Multi-document support** - Index multiple IRCs simultaneously
2. **Conversation memory** - Multi-turn dialogue with context
3. **Evaluation dashboard** - Built-in performance metrics
4. **Additional embedding models** - Cohere, Voyage AI
5. **Export functionality** - Export responses as PDF/Word

## 📞 Questions?

Open an issue with the `question` label or reach out to the maintainer.
