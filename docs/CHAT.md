# Pandora chat page

URL: https://chatbotapi.haho.ai/chat/

Single secret-field login follows the Project Hub at prototype.doneisbetter.com: enter the secret and press Open. No username or browser Basic Auth dialog. Owner-selected secret is recorded only in private/chat-access.txt. Server stores its SHA-256 hash in /etc/narimato-chat.env, mode 600. This deliberately simple shared password is for the owner's personal chat, not a multi-user identity system.

After login: type a message, press Send or Enter; Shift+Enter adds a newline. New chat clears the current conversation. Lock clears the session cookie. Conversation is held only in the tab's memory, not browser storage or a database. Recent history is bounded to fit the small model; older text drops out. Closing/reloading clears displayed history.

Architecture: Caddy proxies /chat and /chat/* to a standard-library Python service on 127.0.0.1:8088. Source is in chat/ locally and /opt/narimato-chat remotely. The systemd unit is config/narimato-chat.service, deployed as /etc/systemd/system/narimato-chat.service. DynamicUser, restricted filesystem, and 192 MB service memory cap are set. Service restarts on failure and starts at boot. Restart clears in-memory sessions.

Secure/HttpOnly/SameSite Strict cookie grants chat access for up to 30 days, or until server restart; no bearer project keys reach the browser. POST requests enforce same origin. Generation uses the authenticated shared gateway on loopback 8090 with reasoning disabled, a 256 output-token cap, 8192-token runtime context and token-budgeted recent turns. The internal `GATEWAY_PANDORA_KEY` stays in the root-only chat environment; no browser bearer key is used. A single chat worker returns 429 if busy; accepted replies join the same FIFO scheduler as project text and Camera images. See [job routing and queue operations](JOB-ROUTER.md).

Commands:

```sh
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl status narimato-chat --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'journalctl -u narimato-chat -n 50 --no-pager'
ssh -i /Users/chappie/.ssh/hetzner_ai root@2.31.100.246 'systemctl restart narimato-chat'
```

To deploy edits: copy chat sources to /opt/narimato-chat, retain readable mode 644 and directory 755, restart the service. The password environment is read by systemd; never copy a plaintext password into public code. To rotate it, replace CHAT_PASSWORD_HASH in the root-only environment file with the SHA-256 hash of the owner's new password, restart service and update restricted local credentials. Update service configuration via daemon-reload if its unit changes.

Caddy routes for bearer-authenticated /v1/models and /v1/chat/completions remain intact. Pre-chat rollback configuration is at /opt/narimato-ai/Caddyfile.before-chat (sensitive). To remove chat, remove its @chat/handle route, validate/reload Caddy and disable/stop narimato-chat; preserve API routes.

Verification uses real public HTTPS: login form, unauthenticated chat refusal, wrong password refusal, successful session login, generated response, logout, and existing project authentication. No full browser visual test has been performed. A password attempt delay is present but comprehensive login rate limiting is not implemented.

The active text route is now Granite 4 1B Hybrid. Pandora submits `model: auto` and follows the server assignment. Its system instruction names the chat persona Pandora and asks it not to invent its developer/model identity. Natural-language self-identification is not a reliable model inventory; check `/v1/job-types` or the completion model field.

The chat response now includes the actual gateway completion model, displayed below the composer after a reply. This footer comes from response metadata rather than the model’s self-description. Refresh the page to load updated UI code; old conversation history may contain previous Qwen replies.

## Larger context deployment, 2026-10-27

See CHATBOT-CONTEXT.md for rationale and tests. The UI keeps up to thirty previous messages and accepts 24000 characters per message. chat/context.py token-counts the system instruction and recent turns, drops oldest turns as needed, reports omitted history and rejects an oversized newest message. The backend submits/polls async gateway jobs and deletes completed jobs after reply delivery; prompts remain non-durable. It now runs in the existing tokenizers-enabled venv. Service restart requires re-entering the same password. The browser/history changes were verified through HTTP and source/syntax checks, not full browser visual testing.
