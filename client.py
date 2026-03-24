import asyncio
import argparse
import uuid
from typing import Optional, Any

import httpx
import websockets
import websockets.exceptions
from pydantic import TypeAdapter, ValidationError
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Button, Label, ListView, ListItem
from textual.reactive import reactive
from textual.message import Message
from textual import work

from ws_protocol import (
    ServerFrame,
    ChunkFrame, DoneFrame, ErrorFrame,
    SendMessageFrame,
)


# ── Custom Textual Messages ───────────────────────────────────────────────────

class StreamChunk(Message):
    def __init__(self, session_id: str, delta: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.delta = delta


class StreamDone(Message):
    def __init__(self, session_id: str, stop_reason: str, input_tokens: int, output_tokens: int) -> None:
        super().__init__()
        self.session_id = session_id
        self.stop_reason = stop_reason
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class StreamError(Message):
    def __init__(self, session_id: str, code: str, message: str) -> None:
        super().__init__()
        self.session_id = session_id
        self.code = code
        self.message = message


class WsConnected(Message):
    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id


class WsDisconnected(Message):
    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id


class ShowSystemMessage(Message):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


# ── Session list item ─────────────────────────────────────────────────────────

class SessionItem(ListItem):
    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id

    def compose(self) -> ComposeResult:
        yield Label(self.session_id[:8] + "…")


# ── Main application ──────────────────────────────────────────────────────────

class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #session-panel {
        width: 32;
        border-right: solid $panel-darken-2;
        padding: 0 1;
    }

    #session-panel-title {
        text-style: bold;
        padding: 1 0;
    }

    #btn-new-session {
        width: 1fr;
        margin-bottom: 1;
    }

    #btn-del-session {
        width: 1fr;
        margin-bottom: 1;
    }

    #session-list {
        height: 1fr;
    }

    #main-panel {
        width: 1fr;
    }

    #message-history {
        height: 1fr;
        padding: 1;
    }

    .user-message {
        background: $surface;
        color: $text;
        padding: 1;
        margin-bottom: 1;
        border-left: thick $accent;
    }

    .assistant-message {
        background: $panel;
        color: $text;
        padding: 1;
        margin-bottom: 1;
        border-left: thick $success;
    }

    .error-message {
        background: $error-darken-3;
        color: $error;
        padding: 1;
        margin-bottom: 1;
    }

    .system-message {
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1;
    }

    #input-row {
        height: 3;
        padding: 0 1;
        dock: bottom;
    }

    #message-input {
        width: 1fr;
    }

    #btn-send {
        width: 8;
    }
    """

    active_session_id: reactive[Optional[str]] = reactive(None)

    def __init__(self, server_url: str) -> None:
        super().__init__()
        self.server_url = server_url.rstrip("/")
        self._ws: Optional[Any] = None
        self._server_frame_adapter: TypeAdapter = TypeAdapter(ServerFrame)
        self._streaming: bool = False
        self._current_assistant_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with Vertical(id="session-panel"):
                yield Label("Sessions", id="session-panel-title")
                yield Button("+ New", id="btn-new-session", variant="success")
                yield Button("✕ Delete", id="btn-del-session", variant="error", disabled=True)
                yield ListView(id="session-list")
            with Vertical(id="main-panel"):
                yield ScrollableContainer(id="message-history")
                with Horizontal(id="input-row"):
                    yield Input(
                        placeholder="Select a session to start chatting…",
                        id="message-input",
                        disabled=True,
                    )
                    yield Button("Send", id="btn-send", variant="primary", disabled=True)
        yield Footer()

    async def on_mount(self) -> None:
        await self._refresh_sessions()

    # ── Session management ────────────────────────────────────────────────────

    async def _refresh_sessions(self) -> None:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(f"{self.server_url}/sessions")
                resp.raise_for_status()
                sessions = resp.json()
        except Exception as e:
            self._notify_system(f"Could not load sessions: {e}")
            return

        list_view = self.query_one("#session-list", ListView)
        await list_view.clear()
        for s in sessions:
            await list_view.append(SessionItem(s["session_id"]))

    async def _create_session(self) -> None:
        session_id = str(uuid.uuid4())
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    f"{self.server_url}/session",
                    json={"session_id": session_id},
                )
                resp.raise_for_status()
        except Exception as e:
            self._notify_system(f"Could not create session: {e}")
            return

        list_view = self.query_one("#session-list", ListView)
        item = SessionItem(session_id)
        await list_view.append(item)
        await self._select_session(session_id)

    async def _delete_session(self) -> None:
        if self.active_session_id is None:
            return
        session_id = self.active_session_id
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.delete(f"{self.server_url}/session/{session_id}")
                resp.raise_for_status()
        except Exception as e:
            self._notify_system(f"Could not delete session: {e}")
            return

        self._ws = None
        self._streaming = False
        self.active_session_id = None

        list_view = self.query_one("#session-list", ListView)
        for item in list_view.query(SessionItem):
            if item.session_id == session_id:
                await item.remove()
                break

        self._clear_history()
        self._set_input_enabled(False)
        self.query_one("#btn-del-session", Button).disabled = True

    async def _select_session(self, session_id: str) -> None:
        self._ws = None
        self._streaming = False
        self._current_assistant_text = ""
        self.active_session_id = session_id

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(f"{self.server_url}/session/{session_id}")
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self._notify_system(f"Could not load session history: {e}")
            return

        self._clear_history()
        history = self.query_one("#message-history", ScrollableContainer)
        for msg in data.get("messages", []):
            css_class = "user-message" if msg["role"] == "user" else "assistant-message"
            await history.mount(Static(msg["content"], classes=f"message {css_class}"))
        history.scroll_end(animate=False)

        self.query_one("#btn-del-session", Button).disabled = False
        self._connect_ws(session_id)

    # ── WebSocket worker ──────────────────────────────────────────────────────

    @work(exclusive=True, group="ws-connection")
    async def _connect_ws(self, session_id: str) -> None:
        ws_base = (
            self.server_url
            .replace("http://", "ws://")
            .replace("https://", "wss://")
        )
        uri = f"{ws_base}/session/{session_id}/ws"
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                self.post_message(WsConnected(session_id))
                async for raw in ws:
                    try:
                        frame = self._server_frame_adapter.validate_json(raw)
                    except ValidationError:
                        continue
                    if isinstance(frame, ChunkFrame):
                        self.post_message(StreamChunk(session_id, frame.delta))
                    elif isinstance(frame, DoneFrame):
                        self.post_message(StreamDone(
                            session_id,
                            frame.stop_reason,
                            frame.input_tokens,
                            frame.output_tokens,
                        ))
                    elif isinstance(frame, ErrorFrame):
                        self.post_message(StreamError(session_id, frame.code, frame.message))
        except websockets.exceptions.ConnectionClosedError as e:
            self.post_message(StreamError(session_id, "connection_closed", str(e)))
        except OSError as e:
            self.post_message(StreamError(session_id, "connection_failed", f"Cannot connect to server: {e}"))
        except Exception as e:
            self.post_message(StreamError(session_id, "error", str(e)))
        finally:
            self._ws = None
            self.post_message(WsDisconnected(session_id))

    # ── Send message ──────────────────────────────────────────────────────────

    async def _send_message(self) -> None:
        if self._streaming:
            return
        input_widget = self.query_one("#message-input", Input)
        content = input_widget.value.strip()
        if not content:
            return
        if self._ws is None:
            self._notify_system("Not connected to session.")
            return

        input_widget.value = ""
        self._streaming = True
        self._current_assistant_text = ""
        self._set_input_enabled(False)

        history = self.query_one("#message-history", ScrollableContainer)
        await history.mount(Static(content, classes="message user-message"))
        await history.mount(Static("", classes="message assistant-message"))
        history.scroll_end(animate=False)

        frame = SendMessageFrame(content=content)
        await self._ws.send(frame.model_dump_json())

    # ── Textual message handlers ──────────────────────────────────────────────

    def on_ws_connected(self, event: WsConnected) -> None:
        if event.session_id == self.active_session_id:
            self._set_input_enabled(True)

    def on_ws_disconnected(self, event: WsDisconnected) -> None:
        if event.session_id == self.active_session_id:
            self._set_input_enabled(False)
            self._streaming = False

    def on_stream_chunk(self, event: StreamChunk) -> None:
        if event.session_id != self.active_session_id:
            return
        self._current_assistant_text += event.delta
        history = self.query_one("#message-history", ScrollableContainer)
        bubbles = list(history.query(".assistant-message"))
        if bubbles:
            bubbles[-1].update(self._current_assistant_text)
            history.scroll_end(animate=False)

    def on_stream_done(self, event: StreamDone) -> None:
        if event.session_id != self.active_session_id:
            return
        self._streaming = False
        self._current_assistant_text = ""
        self._set_input_enabled(True)

    async def on_stream_error(self, event: StreamError) -> None:
        if event.session_id != self.active_session_id:
            return
        self._streaming = False
        self._current_assistant_text = ""
        self._set_input_enabled(True)
        history = self.query_one("#message-history", ScrollableContainer)
        await history.mount(
            Static(f"[{event.code}] {event.message}", classes="message error-message")
        )
        history.scroll_end(animate=False)

    async def on_show_system_message(self, event: ShowSystemMessage) -> None:
        history = self.query_one("#message-history", ScrollableContainer)
        await history.mount(Static(event.text, classes="system-message"))
        history.scroll_end(animate=False)

    # ── Button / input event handlers ─────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-new-session":
            await self._create_session()
        elif event.button.id == "btn-del-session":
            await self._delete_session()
        elif event.button.id == "btn-send":
            await self._send_message()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "message-input":
            await self._send_message()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, SessionItem):
            return
        if event.item.session_id != self.active_session_id:
            await self._select_session(event.item.session_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_history(self) -> None:
        self.query_one("#message-history", ScrollableContainer).remove_children()

    def _set_input_enabled(self, enabled: bool) -> None:
        self.query_one("#message-input", Input).disabled = not enabled
        self.query_one("#btn-send", Button).disabled = not enabled

    def _notify_system(self, text: str) -> None:
        self.post_message(ShowSystemMessage(text))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="client", description="Chat client.")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8000",
        help="Server URL (default: http://127.0.0.1:8000)",
    )
    args = parser.parse_args()
    ChatApp(server_url=args.server).run()


if __name__ == "__main__":
    main()
