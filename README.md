# BYOAI Orchestrator

## Overview

The BYOAI Orchestrator manages and coordinates the deployment of agents and execution of workflows across various Docker and Kubernetes environments. It automates agent registration, task execution, and workflow management, providing a flexible architecture for distributed systems.

### Features
- Automatic agent registration and deployment.
- Workflow management and task execution across multiple agents.
- Support for Docker and Kubernetes-based agents.
- Flask API for easy integration and task management.

### Requirements
- Docker
- Python 3.8+
- Flask

## Installation

### 1. Clone the Repository:

```bash
git clone https://github.com/rabbidave/byoai.git
cd byoai
```

### 2. Install Python Dependencies:

```bash
pip install -r requirements.txt
```

This will install all required packages, including Flask, `requests`, and `pyyaml`.

### 3. Environment Variables:

Ensure the following environment variables are set. They can be set directly in the shell or in your `docker-compose.yml` (shown later):

| Variable                | Default Value               | Description                                                  |
|-------------------------|-----------------------------|--------------------------------------------------------------|
| `AGENT_API_PORT`         | 5000                        | The port where the agent listens.                            |
| `AGENT_MANAGER_API_PORT` | 5001                        | The port where the orchestrator listens.                     |
| `DEFAULT_NETWORK`        | `bridge`                    | The Docker network to use for communication.                 |
| `WORKFLOW_DIR`           | `/app/workflows`            | The directory where workflow files are stored.               |
| `AGENT_IMAGE`            | `your-agent-image:latest`   | The Docker image to be used for agents.                      |
| `AGENT_NAME`             | (set dynamically)           | The name of the agent.                                       |
| `AGENT_WORKFLOW`         | (set dynamically per agent) | The workflow file passed to the agent (used internally).      |

## Running the Orchestrator

The orchestrator can be run in two modes:
1. **Default Workflow Mode** (no workflow file provided).
2. **File-Based Workflow Mode** (specify a workflow file).

### Step-by-Step: Running the Default Workflow

In this mode, the orchestrator will automatically create and run a simple default workflow.

1. **Start the Orchestrator in Default Workflow Mode:**

   ```bash
   python byoai-script.py agent-manager-mode
   ```

   This will start the orchestrator and execute the default workflow. The default workflow simply executes a basic task on a local agent (orchestrator itself).

   **Example Default Workflow:**

   ```yaml
   tasks:
     - name: "sample-task"
       command: "echo 'Running sample task!'"
       agent: "local-agent"

   agents:
     - name: "local-agent"
       type: "docker"
   ```

2. **Logs and Output**:
   - The orchestrator will log the task output directly to the console.
   - The agent registration and workflow task status will also be logged for monitoring.

### Step-by-Step: Running a File-Based Workflow

To run a more complex workflow from a file, follow the steps below.

1. **Create a Workflow YAML File**:

   Create a YAML file that defines your workflow. Save it in a directory mounted as the `WORKFLOW_DIR` (e.g., `/app/workflows` inside the container).

   **Example Workflow (`example_workflow.yml`)**:

   ```yaml
   tasks:
     - name: "task1"
       command: "echo 'Executing task 1'"
       agent: "docker-agent"

     - name: "task2"
       command: "echo 'Executing task 2'"
       agent: "docker-agent"

   agents:
     - name: "docker-agent"
       type: "docker"
       volume: "./data:/app/data"
   ```

   This workflow defines two tasks, `task1` and `task2`, both of which are executed on a Docker agent named `docker-agent`.

2. **Mount Workflow Volume**:

   Ensure the workflow directory is mounted in the orchestrator and agent containers. Update the `docker-compose.yml` to mount your local workflows directory.

   **`docker-compose.yml` Example**:

   ```yaml
   version: "3.9"
   services:
     orchestrator:
       image: your-orchestrator-image:latest
       container_name: orchestrator
       ports:
         - "5001:5001"
       environment:
         - DEFAULT_NETWORK=bridge
         - AGENT_IMAGE=your-agent-image:latest
         - AGENT_API_PORT=5000
         - AGENT_MANAGER_API_PORT=5001
         - WORKFLOW_DIR=/app/workflows
       volumes:
         - ./workflows:/app/workflows  # Mount host workflows directory to /app/workflows in the container
       networks:
         - byoai-network

     docker-agent:
       image: your-agent-image:latest
       container_name: docker-agent
       environment:
         - ORCHESTRATOR_URL=http://orchestrator:5001
         - AGENT_API_PORT=5000
       volumes:
         - ./workflows:/app/workflows  # Mount the same directory in the agent
       depends_on:
         - orchestrator
       networks:
         - byoai-network
       entrypoint: sh -c "curl -X POST -H 'Content-Type: application/json' -d '{\"name\": \"docker-agent\", \"url\": \"http://`hostname -i`:5000\", \"type\": \"docker\"}' $ORCHESTRATOR_URL/register && python /app/agent.py"

   networks:
     byoai-network:
       driver: bridge
   ```

3. **Run the Orchestrator with File-Based Workflow:**

   To run a file-based workflow, provide the path to the workflow YAML file using the `--workflow` or `-f` argument:

   ```bash
   python byoai-script.py --workflow /app/workflows/example_workflow.yml
   ```

   This will trigger the orchestrator to execute the workflow defined in `example_workflow.yml`.

4. **Monitor Execution**:

   The orchestrator will log the progress and results of the workflow execution. You can monitor task execution and agent registration in the logs.

## Sharing Workflows with Agents Using Volumes

If your agents need access to workflow files, you can mount a volume in `docker-compose.yml`:

```yaml
version: "3.9"
services:
  orchestrator:
    # ...
    volumes:
      - ./workflows:/app/workflows  # Mount host workflows directory to /app/workflows in the container
  docker-agent:
    # ...
    volumes:
      - ./workflows:/app/workflows  # Mount the same directory in the agent
```

Ensure the `WORKFLOW_DIR` environment variable in `byoai-script.py` and the mount point in the containers are consistent (e.g., both `/app/workflows`).

If you are baking workflows into the agent image, then no volume mounting is needed. Set the `WORKFLOW_DIR` environment variable appropriately in the Dockerfile and in `byoai-script.py` for the agent. For example, if the workflow is placed at `/app/workflows/default.yaml` in the agent image, you do not need to mount volumes. Just pass the full path to `byoai-script.py` and `agent.py`.

## API Endpoints

#### 1. **Register Agent (`/register`)**

* **Request (POST):**
```json
{
  "name": "agent1",
  "url": "http://agent1_ip:5000",
  "type": "docker"
}
```

* **Response (200 OK):**
```json
{
  "status": "success"
}
```

#### 2. **Deploy Agent (`/deploy_agent`)**

* **Request (POST):**
```json
{
  "name": "agent2",
  "type": "docker",
  "image": "your-agent-image:latest",
  "workflow": "workflow2.yaml",  # Optional workflow file
  "volume": "./data:/app/data"  # Optional volume mounts
}
```

* **Response (200 OK):**
```json
{
  "status": "Agent deployment initiated"
}
```

#### 3. **Run Workflow (`/workflow`)**

* **Request (POST):**
```json
{
  "workflow": "example_workflow.yml"  # Path to the workflow file
}
```

* **Response (200 OK):**
```json
{
  "status": "workflow execution started"
}
```

## Troubleshooting

### 1. Agents Are Not Registering

- Ensure that the orchestrator is running and accessible to the agents.
- Verify that the `ORCHESTRATOR_URL` environment variable in the agents is set correctly.
- Check the network configuration in `docker-compose.yml` to ensure agents are on the same network as the orchestrator.
- Review the agent and orchestrator logs for error messages.

### 2. Workflows Are Not Executing

- Ensure the workflow file exists in the correct directory and is mounted in the containers (check the `WORKFLOW_DIR`).
- Check the logs of both the orchestrator and agents for any errors related to task execution.
- Verify that the `AGENT_WORKFLOW` environment variable is set correctly in the Docker container.

### 3. Docker-Related Issues

- Ensure Docker is installed and running on your machine.
- Run `docker ps` to ensure the containers are running as expected.
- If a container fails to start, check the logs using `docker logs <container_name>`.

## Docker and Agent Deployment

### Using Docker Compose:

Run the following to start the orchestrator and agent:

```bash
docker-compose up
```
