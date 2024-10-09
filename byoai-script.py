#!/usr/bin/env python

import yaml
import subprocess
import os
import requests
import json
import time
import argparse
from flask import Flask, request, jsonify
import logging

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants (now using environment variables)
AGENT_API_PORT = int(os.environ.get("AGENT_API_PORT", 5000))
AGENT_MANAGER_API_PORT = int(os.environ.get("AGENT_MANAGER_API_PORT", 5001))
DEFAULT_NETWORK = os.environ.get("DEFAULT_NETWORK", "bridge")  # Default to 'bridge'
WORKFLOW_DIR = os.environ.get("WORKFLOW_DIR", "/app/workflows")
IMAGE_NAME = os.environ.get("AGENT_IMAGE", "your-agent-image:latest")

registered_agents = {}

def handle_error(func):
    """Decorator to handle and log errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper

@handle_error
def run_task_on_agent(task, agent_url):
    """Run a task on a specified agent."""
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(f"{agent_url}/task", json=task, headers=headers, timeout=600)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with agent: {e}")
        return None

@handle_error
def execute_local_task(task):
    """Execute a task locally."""
    command = task.get('command')
    if command:
        try:
            process = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, cwd="/app")
            logger.info(f"Task '{task.get('name', 'Unnamed task')}' output: {process.stdout}")
            return {"status": "success", "output": process.stdout, "returncode": process.returncode}
        except subprocess.CalledProcessError as e:
            logger.error(f"Task '{task.get('name', 'Unnamed task')}' error: {e.stderr}")
            return {"status": "error", "message": e.stderr, "returncode": e.returncode}
    return {"error": "No command provided"}

def wait_for_agent(agent_name):
    """Wait for agent registration and health check."""
    max_attempts = 60
    attempts = 0
    while attempts < max_attempts:
        if agent_name in registered_agents:
            agent_url = registered_agents[agent_name]
            if check_agent_health(agent_url):
                return agent_url
        time.sleep(10)
        attempts += 1
    raise Exception(f"Agent {agent_name} did not become ready within timeout.")

def check_agent_health(agent_url):
    """Check the health of an agent."""
    try:
        response = requests.get(f"{agent_url}/health", timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

@handle_error
def run_workflow(workflow_file=None):
    """Run the specified workflow, or default workflow if none provided."""
    if workflow_file is None or not os.path.exists(workflow_file):
        # Create and run default workflow if no workflow is provided
        workflow = {
            'tasks': [{'name': 'sample-task', 'command': 'echo "Running sample task!"', 'agent': 'local-agent'}],
            'agents': [{'name': 'local-agent', 'type': 'docker'}],
        }
        logger.info("Running default sample workflow.")
        for task in workflow['tasks']:
            result = execute_local_task(task)
    else:
        with open(workflow_file, 'r') as f:
            workflow = yaml.safe_load(f)
        logger.info(f"Loaded workflow from {workflow_file}.")
        for task in workflow['tasks']:
            agent = task.get('agent')
            if agent:
                agent_config = next((a for a in workflow['agents'] if a['name'] == agent), None)
                if agent_config:
                    spawn_agent(agent_config)
                    agent_url = wait_for_agent(agent)
                    result = run_task_on_agent(task, agent_url)
                else:
                    logger.error(f"Agent {agent} not found in workflow.")
            else:
                result = execute_local_task(task)

@handle_error
def spawn_agent(agent_params):
    """Spawn an agent, ensuring no duplicates, and pass environment variables."""
    agent_name = agent_params.get('name')
    agent_type = agent_params.get('type')
    agent_workflow = agent_params.get('workflow')
    agent_volume = agent_params.get('volume')

    # Check if agent is already running
    try:
        result = subprocess.run(['docker', 'ps', '--filter', f'name={agent_name}'], capture_output=True, text=True, check=True)
        if agent_name in result.stdout:
            logger.info(f"Agent {agent_name} is already running.")
            return
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking Docker: {e}")

    # Spawn new Docker agent
    docker_cmd = [
        "docker", "run", "-d",
        "--name", agent_name,
        "--network", DEFAULT_NETWORK,
        "-p", f"{AGENT_API_PORT}:{AGENT_API_PORT}",
        "-e", f"AGENT_
