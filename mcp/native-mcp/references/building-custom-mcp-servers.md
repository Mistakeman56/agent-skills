# Building Custom MCP Servers (Stdio Transport)

When building a custom MCP server that communicates over stdin/stdout, the wire protocol uses **JSON-RPC 2.0** with specific MCP method names.

## Protocol Format

### Initialization (mandatory)

On startup, the server SHOULD send a `ready` notification:

```json
{"jsonrpc":"2.0","method":"ready","params":{}}
```

The client then sends `initialize`:

```json
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes-agent","version":"1.0"}},"id":1}
```

Respond with server capabilities:

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"my-server","version":"1.0"}}}
```

The client then sends `notifications/initialized` (no response needed).

### Tool Discovery

**Request (from client):**
```json
{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}
```

**Response (from server):**
```json
{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"my_tool","description":"Does something","inputSchema":{"type":"object","properties":{"param1":{"type":"string"}},"required":["param1"]}}]}}
```

### Tool Call

**Request:**
```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"my_tool","arguments":{"param1":"value"}},"id":2}
```

**Response:**
```json
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"result string"}]}}
```

### Error Response

```json
{"jsonrpc":"2.0","id":2,"error":{"code":-32603,"message":"Error description"}}
```

### Ping / Keepalive

```json
{"jsonrpc":"2.0","method":"ping","params":{},"id":99}
```
Respond with `{"jsonrpc":"2.0","id":99,"result":"pong"}`.

## Key Method Names (NOT the same as older conventions)

| Correct | Wrong |
|---------|-------|
| `tools/list` | `list_tools` |
| `tools/call` | `call_tool` |
| `notifications/initialized` | (omitted) |
| `ping` | (not needed) |

## Common Mistakes

1. **Using wrong method names** — `list_tools` instead of `tools/list` → server won't be discovered but process stays alive → `CancelledError` timeout
2. **Omitting readiness signal** — some Hermes versions expect an immediate stdout message to confirm the server started
3. **Blocking imports at module level** — Hermes has a short (configurable) initial timeout. Heavy imports (PyPDF2, sentence-transformers, etc.) at module level cause timeout. Use lazy `import` inside tool handlers instead.
4. **Forgetting `content` envelope** — tool call responses MUST wrap text in `{"content": [{"type": "text", "text": "..."}]}`, not just return raw strings.

## Python Reference Implementation

```python
import sys, json

def handle(msg):
    method = msg.get("method","")
    if method == "tools/list":
        return {"jsonrpc":"2.0","id":msg["id"],"result":{"tools":[...]}}
    elif method == "tools/call":
        name = msg.get("params",{}).get("name","")
        args = msg.get("params",{}).get("arguments",{})
        result = do_something(name, args)
        return {"jsonrpc":"2.0","id":msg["id"],"result":{"content":[{"type":"text","text":result}]}}
    elif method == "ping":
        return {"jsonrpc":"2.0","id":msg["id"],"result":"pong"}
    return None  # notifications: no response

# Send ready signal
sys.stdout.write('{"jsonrpc":"2.0","method":"ready","params":{}}\n')
sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        resp = handle(json.loads(line))
        if resp:
            sys.stdout.write(json.dumps(resp)+'\n')
            sys.stdout.flush()
    except: pass
```

## Testing

Test the server directly before adding to config:

```bash
echo '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}' | timeout 3 python3 my_server.py
```

If this returns the tool list, the server works. Any subsequent `CancelledError` from the gateway is a timeout issue — increase `connect_timeout` in config.
