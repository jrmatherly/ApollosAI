<a name="readme-top"></a>

<div align="center">
  <img src="https://raw.githubusercontent.com/OpenHands/docs/main/openhands/static/img/logo.png" alt="Logo" width="200">
  <h1 align="center" style="border-bottom: none">ApollosAI: AI-Driven Development</h1>
</div>

<hr>

🙌 Welcome to ApollosAI

There are a few ways to work with ApollosAI:

### ApollosAI Software Agent SDK
The SDK is a composable Python library that contains all of our agentic tech. It's the engine that powers everything else below.

Define agents in code, then run them locally, or scale to 1000s of agents in the cloud.

[Check out the docs](https://docs.apollosai.dev/sdk) or [view the source](https://github.com/jrmatherly/software-agent-sdk/)

### ApollosAI CLI
The CLI is the easiest way to start using ApollosAI. The experience will be familiar to anyone who has worked
with e.g. Claude Code or Codex. You can power it with Claude, GPT, or any other LLM.

[Check out the docs](https://docs.apollosai.dev/apollosai/usage/run-openhands/cli-mode) or [view the source](https://github.com/OpenHands/OpenHands-CLI)

### ApollosAI Local GUI
Use the Local GUI for running agents on your laptop. It comes with a REST API and a single-page React application.
The experience will be familiar to anyone who has used Devin or Jules.

[Check out the docs](https://docs.apollosai.dev/apollosai/usage/run-apollosai/local-setup) or view the source in this repo.

### OpenHands Enterprise
Large enterprises can work with us to self-host OpenHands Cloud in their own VPC, via Kubernetes.
OpenHands Enterprise can also work with the CLI and SDK above.

OpenHands Enterprise is source-available--you can see all the source code here in the enterprise/ directory,
but you'll need to purchase a license if you want to run it for more than one month.

All our work is available under the MIT license, except for the `enterprise/` directory in this repository (see the [enterprise license](enterprise/LICENSE) for details).

The core `openhands` and `agent-server` Docker images are fully MIT-licensed as well.
