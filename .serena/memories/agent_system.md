# Agent System Architecture

## Core Loop (Pseudocode)
```
while True:
    prompt = agent.generate_prompt(state)
    response = llm.completion(prompt)
    action = agent.parse_response(response)
    observation = runtime.run(action)
    state = state.update(action, observation)
```
Actual implementation uses EventStream message passing.

## Control Flow
```
Agent --Actions--> AgentController --Actions--> EventStream --Actions--> Runtime
Runtime --Observations--> EventStream --Observations--> AgentController --State--> Agent
Frontend --Actions--> EventStream
```

## Key Classes
- **LLM**: Wraps LiteLLM for multi-provider completions
- **Agent**: Abstract base; `step(state) -> Action`. Has `self.llm`. Registry pattern.
- **AgentController**: Drives main loop, manages State
- **State**: Current task state (iterations, history, metrics, delegates)
- **EventStream**: Central pub-sub hub for Actions and Observations
- **Runtime**: Executes Actions, returns Observations (Docker, K8s, Local, Remote, CLI)
- **Server/Session**: HTTP broker; Session = EventStream + AgentController + Runtime
- **ConversationManager**: Routes requests to correct Session

## Agent Interface
Every agent must implement:
```python
def step(self, state: "State") -> "Action"
```

## Available Agents
- **CodeActAgent** (production) — function calling, bash, editor, browser, IPython, MCP
- **BrowsingAgent** — web browsing specialist
- **VisualBrowsingAgent** — visual web browsing
- **ReadOnlyAgent** — read-only operations
- **LOCAgent** — lines-of-code focused
- **DummyAgent** — testing/placeholder

## Action Types
- `CmdRunAction` — sandboxed terminal command
- `IPythonRunCellAction` — Jupyter notebook cell execution
- `FileReadAction` / `FileWriteAction` — file operations
- `BrowseURLAction` — web page content
- `AddTaskAction` / `ModifyTaskAction` — subtask management
- `AgentFinishAction` / `AgentRejectAction` — stop control loop
- `MessageAction` — agent or user message

## Observation Types
- `CmdOutputObservation` — command output
- `BrowserOutputObservation` — web page content
- `FileReadObservation` / `FileWriteObservation` — file operation results
- `ErrorObservation` / `SuccessObservation` — status

## Serialization
- `action.to_dict()` — for UI (user-friendly)
- `action.to_memory()` — for LLM (raw, includes exceptions)
- `action_from_dict()` / `observation_from_dict()` — deserialization

## Multi-Agent Delegation
- **Task**: End-to-end user↔system conversation (may span multiple agents)
- **Subtask**: Single agent↔user/agent conversation within a task
- ITERATION is global across agents; LOCAL_ITERATION is per-subtask
- DELEGATE_LEVEL tracks nesting depth
- Example: CodeActAgent delegates to BrowsingAgent for web queries

## State Contents
- Delegate info: root task, subtask, global/local iterations, delegate levels
- Running state: agent state enum, traffic control, confirmation mode, last error
- History: start/end event IDs for session replay
- Metrics: global (task) and local (subtask)
- Extra data: task-specific
