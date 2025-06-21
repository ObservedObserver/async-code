# Async Code Agent

Use Claude Code / CodeX CLI to perform multiple tasks in parallel with a Codex-style UI.

A code agent task management system that provides parallel execution of AI-powered coding tasks. Users can run multiple Claude Code agents simultaneously through a Codex-style web interface, with support for different agents for comparison and evaluation.

![async-code-ui](https://github.com/user-attachments/assets/e490c605-681a-4abb-a440-323e15f1a90d)


![async-code-review](https://github.com/user-attachments/assets/bbf71c82-636c-487b-bb51-6ad0b393c2ef)


## Key Features

- 🤖 **Multi-Agent Support**: Run Claude Code and other AI agents in parallel
- 🔄 **Parallel Task Management**: Execute multiple coding tasks simultaneously  
- 🌐 **Codex-Style Web UI**: Clean interface for managing agent tasks
- 🔍 **Agent Comparison**: Compare outputs from different AI models
- 🐳 **Containerized Execution**: Secure sandboxed environment for each task
- 🔗 **Git Integration**: Automatic repository cloning, commits, and PR creation
- **Selfhost**: Deploy you rown parallel code agent platform.

## Architecture

- **Frontend**: Next.js with TypeScript and TailwindCSS
- **Backend**: Python Flask API with Docker orchestration
- **Agents**: Claude Code (Anthropic) with extensible support for other models
- **Task Management**: Parallel execution system based on container

## Prerequisites

- Docker and Docker Compose installed
- (Optional) Supabase account for persistent data storage

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <this-repo>
   cd async-code
   ```

2. **Create the environment file**
   ```bash
   cp server/.env.example server/.env
   ```
   Edit `server/.env` and set your `ANTHROPIC_API_KEY`. If you are using Supabase, also set `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.

3. **Build and start the stack**
   ```bash
   docker-compose up --build -d
   ```

   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000

## Supabase Setup

1. Create a new project in the [Supabase](https://supabase.com) dashboard.
2. Open the SQL editor and run `db/init_supabase.sql` to create the required tables.
3. Grab your project URL, anon key and service role key from **Project Settings → API** and place them in `server/.env`.

## Usage

1. **Setup GitHub Token**: Enter your GitHub token in the web interface
2. **Configure Repository**: Specify target repository and branch
3. **Select Agent**: Choose your preferred AI agent (Claude Code, etc.)
4. **Submit Tasks**: Start multiple coding tasks in parallel
5. **Compare Results**: Review and compare outputs from different agents
6. **Create PRs**: Generate pull requests from successful tasks

## Environment Variables

```bash
# server/.env
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Flask configuration
FLASK_ENV=production
FLASK_DEBUG=False
```


## Development

```bash
# Run all services
docker-compose up

# Development mode
cd async-code-web && npm run dev  # Frontend
cd server && python main.py      # Backend
```

## Production Deployment

1. Set `FLASK_ENV=production` in `server/.env` and export `NODE_ENV=production` before running the stack.
2. Build and start the containers:
   ```bash
   NODE_ENV=production docker-compose up --build -d
   ```
3. Monitor the logs with:
   ```bash
   docker-compose logs -f
   ```


## License

See LICENSE file for details.

