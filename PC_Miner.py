#!/usr/bin/env python3
"""
MUNEX PoMR Miner – AI Self‑Learning v27 (Terminal + Debug)
- Uses DQN with hardware‑scaled training.
- Prints hashstep progress like a real mining terminal.
- Robust reconnection with exponential backoff and jitter.
- Registry‑based node discovery with fallback to local tunnel files.
- WebSocket ping/pong keeps connection alive.
- Debug: prints every raw message received.
- Wallet format: 0x... (Ethereum‑style).
"""

import asyncio
import websockets
import json
import time
import hashlib
import secrets
import argparse
import logging
import base64
import sys
import random
import os
from collections import deque
from typing import Optional, Tuple, List, Dict
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import aiohttp
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature

# ─── ANSI colors ───
RESET = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
DIM = "\033[2m"

# ─── Banner ───
BANNER = f"""
{MAGENTA}{BOLD}
  █████╗ ██╗      ██████╗  █████╗ ███╗   ███╗██╗███╗   ██╗███████╗██████╗ 
 ██╔══██╗██║     ██╔════╝ ██╔══██╗████╗ ████║██║████╗  ██║██╔════╝██╔══██╗
 ███████║██║     ██║  ███╗███████║██╔████╔██║██║██╔██╗ ██║█████╗  ██████╔╝
 ██╔══██║██║     ██║   ██║██╔══██║██║╚██╔╝██║██║██║╚██╗██║██╔══╝  ██╔══██╗
 ██║  ██║███████╗╚██████╔╝██║  ██║██║ ╚═╝ ██║██║██║ ╚████║███████╗██║  ██║
 ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
{RESET}
{WHITE}────────── AI PoMR MINER v27 (Terminal + Debug) ──────────{RESET}
"""

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ─── Constants ───
REGISTRY_URL = "https://register12345.animax-plorer22.workers.dev"
STEP_INTERVAL = 5
MAZE_SIZE = 64
MAX_MISSES = 3
WALLET_FILE = "miner_wallet.json"
MODEL_FILE = "miner_model.pt"

# ─── Hardware detection ────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if DEVICE.type == "cuda":
    TRAIN_BATCH_SIZE = 128
    TRAIN_EPOCHS_PER_MAZE = 10
elif DEVICE.type == "mps":
    TRAIN_BATCH_SIZE = 64
    TRAIN_EPOCHS_PER_MAZE = 5
else:
    TRAIN_BATCH_SIZE = 32
    TRAIN_EPOCHS_PER_MAZE = 3

# ─── Crypto helpers ──────────────────────────────────────────────
def generate_keypair() -> Tuple[str, str, str]:
    priv = ec.generate_private_key(ec.SECP256K1())
    priv_int = priv.private_numbers().private_value
    priv_hex = priv_int.to_bytes(32, 'big').hex()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    pub_hex = pub_bytes.hex()
    pub_no_prefix = pub_bytes[1:]
    keccak = hashlib.sha3_256(pub_no_prefix).digest()
    addr = '0x' + keccak[-20:].hex()
    return addr, priv_hex, pub_hex

def sign_message(private_key_hex: str, message: str) -> str:
    priv_int = int(private_key_hex, 16)
    priv_key = ec.derive_private_key(priv_int, ec.SECP256K1())
    signature = priv_key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(signature)
    return r.to_bytes(32, 'big').hex() + s.to_bytes(32, 'big').hex()

def pubkey_hex_from_priv(priv_hex: str) -> str:
    priv_int = int(priv_hex, 16)
    priv_key = ec.derive_private_key(priv_int, ec.SECP256K1())
    pub = priv_key.public_key()
    x = pub.public_numbers().x.to_bytes(32, 'big')
    y = pub.public_numbers().y.to_bytes(32, 'big')
    return (b'\x04' + x + y).hex()

def save_wallet(wallet: str, privkey: str):
    with open(WALLET_FILE, 'w') as f:
        json.dump({'wallet': wallet, 'privkey': privkey}, f)
    os.chmod(WALLET_FILE, 0o600)

def load_wallet() -> Optional[Tuple[str, str]]:
    try:
        with open(WALLET_FILE, 'r') as f:
            data = json.load(f)
            return data.get('wallet'), data.get('privkey')
    except:
        return None

# ─── AI Model (DQN) ──────────────────────────────────────────────
class DQN(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 256, output_dim: int = 4):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)

class ReplayBuffer:
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones = zip(*batch)
        return (np.array(states, dtype=np.float32),
                np.array(actions, dtype=np.int64),
                np.array(rewards, dtype=np.float32),
                np.array(next_states, dtype=np.float32),
                np.array(dones, dtype=np.uint8))

    def __len__(self):
        return len(self.buffer)

# ─── AI Miner ──────────────────────────────────────────────────
class AIMiner:
    def __init__(self, node_url: str = "", wallet: str = "", privkey: str = "", miner_id: str = ""):
        self.node_url = node_url
        self.wallet = wallet
        self.privkey = privkey
        self.miner_id = miner_id
        self.pubkey_hex = ""

        # Load or create wallet
        if not self.wallet or not self.privkey:
            loaded = load_wallet()
            if loaded:
                self.wallet, self.privkey = loaded
                print(f"{CYAN}>>> Loaded wallet from file:{RESET} {self.wallet}")
                self.pubkey_hex = pubkey_hex_from_priv(self.privkey)
            else:
                self.wallet, self.privkey, self.pubkey_hex = generate_keypair()
                print(f"\n{CYAN}>>> Generated new wallet:{RESET} {self.wallet}")
                print(f"{CYAN}>>> Private key (save it):{RESET} {self.privkey[:16]}...")
                save_wallet(self.wallet, self.privkey)
                print(f"{GREEN}>>> Wallet saved to {WALLET_FILE}{RESET}")
        else:
            self.pubkey_hex = pubkey_hex_from_priv(self.privkey)
            print(f"{CYAN}>>> Using wallet:{RESET} {self.wallet}")

        if not self.miner_id:
            self.miner_id = "MCR_MINER_" + hashlib.sha256(f"{self.wallet}{time.time()}{secrets.token_hex(8)}".encode()).hexdigest()[:32].upper()
        print(f"{CYAN}>>> Miner ID:{RESET} {self.miner_id}")

        # Maze state
        self.maze = None
        self.start = None
        self.goal = None
        self.current_pos = None
        self.block_id = -1
        self.step_interval = STEP_INTERVAL
        self.deadline = 0
        self.round_active = False
        self.steps_taken = 0
        self.total_steps = 0
        self.maze_size = 0
        self.total_possible_steps = 0

        # Uptime
        self.start_time = time.time()
        self.uptime_seconds = 0
        self.today_uptime = 0

        # AI
        self.input_dim = 5 * 5 + 3
        self.model = DQN(self.input_dim).to(DEVICE)
        self.target_model = DQN(self.input_dim).to(DEVICE)
        self.target_model.load_state_dict(self.model.state_dict())
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-3)
        self.replay_buffer = ReplayBuffer(capacity=10000)
        self.train_step = 0
        self.epsilon = 0.2
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995

        if os.path.exists(MODEL_FILE):
            try:
                checkpoint = torch.load(MODEL_FILE, map_location=DEVICE)
                self.model.load_state_dict(checkpoint['model'])
                self.target_model.load_state_dict(checkpoint['model'])
                self.optimizer.load_state_dict(checkpoint['optimizer'])
                self.train_step = checkpoint.get('step', 0)
                self.epsilon = checkpoint.get('epsilon', 0.2)
                print(f"{GREEN}>>> Loaded AI model from {MODEL_FILE} (steps={self.train_step}){RESET}")
            except Exception as e:
                print(f"{YELLOW}⚠️ Could not load model: {e}{RESET}")

        self.websocket = None
        self.running = True
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        self.jitter = 0.2

    # ─── AI helpers ──────────────────────────────────────────────

    def get_local_view(self, maze, pos):
        half = 2
        view = np.zeros((5, 5), dtype=np.float32)
        for dy in range(-half, half+1):
            for dx in range(-half, half+1):
                ny = pos[1] + dy
                nx = pos[0] + dx
                if 0 <= nx < len(maze) and 0 <= ny < len(maze):
                    view[dy+half][dx+half] = 1.0 if maze[ny][nx] else 0.0
                else:
                    view[dy+half][dx+half] = 1.0
        return view.flatten()

    def get_state(self, maze, pos, goal):
        view = self.get_local_view(maze, pos)
        dx = goal[0] - pos[0]
        dy = goal[1] - pos[1]
        dist = np.sqrt(dx*dx + dy*dy) / (len(maze) * 1.414)
        angle = np.arctan2(dy, dx)
        sin_angle = np.sin(angle)
        cos_angle = np.cos(angle)
        return np.concatenate([view, [dist, sin_angle, cos_angle]])

    def choose_action(self, state, epsilon):
        if random.random() < epsilon:
            return random.randint(0, 3)
        state_t = torch.FloatTensor(state).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            q_values = self.model(state_t)
        return q_values.argmax().item()

    def train_model(self):
        if len(self.replay_buffer) < TRAIN_BATCH_SIZE:
            return
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(TRAIN_BATCH_SIZE)
        states = torch.FloatTensor(states).to(DEVICE)
        actions = torch.LongTensor(actions).unsqueeze(1).to(DEVICE)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(DEVICE)
        next_states = torch.FloatTensor(next_states).to(DEVICE)
        dones = torch.FloatTensor(dones).unsqueeze(1).to(DEVICE)

        q_values = self.model(states).gather(1, actions)
        with torch.no_grad():
            max_next_q = self.target_model(next_states).max(1, keepdim=True)[0]
            target = rewards + (1 - dones) * 0.99 * max_next_q

        loss = F.mse_loss(q_values, target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        self.train_step += 1

        if self.train_step % 100 == 0:
            self.target_model.load_state_dict(self.model.state_dict())

    def save_model(self):
        torch.save({
            'model': self.model.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'step': self.train_step,
            'epsilon': self.epsilon
        }, MODEL_FILE)

    # ─── Maze navigation with terminal output ─────────────────────

    def _compute_hash(self, pos, direction, step):
        """Generate a hash string for the current step."""
        data = f"{self.block_id}{self.miner_id}{pos[0]}{pos[1]}{direction}{step}{time.time()}"
        h = hashlib.sha256(data.encode()).hexdigest()[:8]
        return h

    def _progress_bar(self, current, total, width=40):
        """Return a progress bar string."""
        if total == 0:
            return ""
        percent = current / total
        filled = int(width * percent)
        bar = '█' * filled + '░' * (width - filled)
        return f"{bar} {percent*100:.0f}%"

    async def navigate_maze(self):
        if self.maze is None or self.start is None or self.goal is None:
            return

        pos = self.start
        goal = self.goal
        size = len(self.maze)
        self.maze_size = size
        self.total_possible_steps = size * size * 2  # max steps
        steps = 0
        reward_total = 0
        epsilon = self.epsilon

        print(f"\n{GREEN}>>> Starting maze solve for block {self.block_id}{RESET}")
        print(f"{CYAN}Maze size: {size}x{size} | Goal: {goal}{RESET}")
        print(f"{YELLOW}Press Ctrl+C to stop miner{RESET}\n")

        while pos != goal and steps < self.total_possible_steps:
            state = self.get_state(self.maze, pos, goal)
            action_idx = self.choose_action(state, epsilon)
            direction = ["up", "down", "left", "right"][action_idx]
            dir_map = {"up": (0,-1), "down": (0,1), "left": (-1,0), "right": (1,0)}
            dx, dy = dir_map[direction]
            nx, ny = pos[0] + dx, pos[1] + dy

            if 0 <= nx < size and 0 <= ny < size and not self.maze[ny][nx]:
                next_pos = (nx, ny)
                reward = 100 if next_pos == goal else -1
            else:
                next_pos = pos
                reward = -10

            next_state = self.get_state(self.maze, next_pos, goal)
            self.replay_buffer.push(state, action_idx, reward, next_state, next_pos == goal)

            if len(self.replay_buffer) >= TRAIN_BATCH_SIZE:
                self.train_model()

            pos = next_pos
            steps += 1
            reward_total += reward
            self.current_pos = pos
            self.steps_taken = steps

            # ─── PRINT HASHSTEP ──────────────────────────────────────
            hash_val = self._compute_hash(pos, direction, steps)
            progress = self._progress_bar(steps, self.total_possible_steps)
            print(f"Hashstep {steps}/{self.total_possible_steps}: 0x{hash_val} (x:{pos[0]:2d}, y:{pos[1]:2d})  {progress}")

            await self.send_move(direction)
            await asyncio.sleep(0.1)

            if pos == goal:
                print(f"\n{GREEN}🎉 BLOCK FOUND! 🎉{RESET}")
                print(f"{GREEN}Reached goal in {steps} steps!{RESET}")
                break

        # Final training after maze
        for _ in range(TRAIN_EPOCHS_PER_MAZE):
            if len(self.replay_buffer) >= TRAIN_BATCH_SIZE:
                self.train_model()
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        if steps > 0 and self.train_step % 50 == 0:
            self.save_model()

        return pos == goal

    async def send_move(self, direction):
        if self.websocket is None:
            return
        message = f"{self.block_id}{self.miner_id}{direction}"
        signature = sign_message(self.privkey, message)
        move_msg = {
            "type": "maze_move",
            "miner_id": self.miner_id,
            "direction": direction,
            "signature": signature
        }
        try:
            await self.websocket.send(json.dumps(move_msg))
        except websockets.exceptions.ConnectionClosed:
            print(f"{YELLOW}⚠️ Connection closed while sending move{RESET}")
            self.round_active = False

    # ─── Registry & connection ─────────────────────────────────

    async def is_connected(self) -> bool:
        if self.websocket is None:
            return False
        try:
            from websockets import State
            return self.websocket.state == State.OPEN
        except (ImportError, AttributeError):
            return not self.websocket.closed

    def read_local_tunnel(self) -> Optional[str]:
        try:
            for path in [".", ".."]:
                for fname in ["tunnel_url.txt", "localtunnel_url.txt"]:
                    file_path = os.path.join(path, fname)
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            url = f.read().strip()
                            if url:
                                if url.startswith(("ws://", "wss://")):
                                    return url
                                else:
                                    return f"wss://{url.replace('https://', '').replace('http://', '')}/ws"
        except Exception:
            pass
        return None

    async def discover_nodes(self) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{REGISTRY_URL}/peers", timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        peers = data.get("peers", [])
                        valid = [p["ws_url"] for p in peers if p.get("ws_url") and p["ws_url"].startswith(("ws://", "wss://"))]
                        random.shuffle(valid)
                        return valid
                    else:
                        return []
        except Exception:
            return []

    async def connect(self, url: str) -> bool:
        try:
            # ─── WebSocket ping/pong to keep connection alive ─────
            self.websocket = await websockets.connect(
                url,
                ping_interval=10,      # send ping every 10s
                ping_timeout=5         # wait 5s for pong
            )
            self.node_url = url
            print(f"{GREEN}✓ Connected to node{RESET}")
            self.reconnect_delay = 1
            return True
        except Exception as e:
            print(f"{RED}✗ Connection failed: {e}{RESET}")
            return False

    async def register(self) -> bool:
        timestamp = int(time.time())
        message = f"{self.miner_id}{self.wallet}{timestamp}"
        signature = sign_message(self.privkey, message)

        reg_msg = {
            "type": "register",
            "miner_id": self.miner_id,
            "wallet": self.wallet,
            "public_key": self.pubkey_hex,
            "signature": signature,
            "timestamp": timestamp,
            "miner_type": "pc_ai"
        }
        print(f"{CYAN}⏳ Registration sent...{RESET}")
        try:
            await self.websocket.send(json.dumps(reg_msg))
        except websockets.exceptions.ConnectionClosed as e:
            print(f"{RED}✗ Connection closed while sending registration: {e}{RESET}")
            return False

        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=15)
        except asyncio.TimeoutError:
            print(f"{RED}✗ Registration timeout{RESET}")
            return False
        except websockets.exceptions.ConnectionClosed as e:
            print(f"{RED}✗ Connection closed while waiting for response: {e}{RESET}")
            return False

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            print(f"{RED}✗ Invalid response: {response}{RESET}")
            return False

        if data.get("type") == "memory_challenge_request":
            seed = data.get("seed")
            commitment = secrets.token_bytes(32)
            commitment_b64 = base64.b64encode(commitment).decode()
            challenge_response = {
                "type": "memory_challenge_response",
                "miner_id": self.miner_id,
                "seed": seed,
                "commitment": commitment_b64
            }
            try:
                await self.websocket.send(json.dumps(challenge_response))
            except websockets.exceptions.ConnectionClosed as e:
                print(f"{RED}✗ Connection closed while sending challenge response: {e}{RESET}")
                return False

            print(f"{CYAN}⏳ Memory challenge sent...{RESET}")
            try:
                result = await asyncio.wait_for(self.websocket.recv(), timeout=15)
            except asyncio.TimeoutError:
                print(f"{RED}✗ Registration result timeout{RESET}")
                return False
            except websockets.exceptions.ConnectionClosed as e:
                print(f"{RED}✗ Connection closed while waiting for result: {e}{RESET}")
                return False

            try:
                res_data = json.loads(result)
            except json.JSONDecodeError:
                print(f"{RED}✗ Invalid result: {result}{RESET}")
                return False

            if res_data.get("type") == "registered":
                balance = res_data.get('confirmed_balance', 0)
                print(f"{GREEN}✅ Registration successful! Balance: {balance} MCX{RESET}")
                await self.send_uptime_ping()
                return True
            else:
                print(f"{RED}✗ Registration failed: {res_data}{RESET}")
                return False
        else:
            print(f"{RED}✗ Unexpected response: {data}{RESET}")
            return False

    async def send_uptime_ping(self):
        self.uptime_seconds = int(time.time() - self.start_time)
        self.today_uptime = self.uptime_seconds
        ping_msg = {
            "type": "uptime_ping",
            "miner_id": self.miner_id,
            "uptime_seconds": self.uptime_seconds,
            "today_uptime": self.today_uptime
        }
        try:
            if await self.is_connected():
                await self.websocket.send(json.dumps(ping_msg))
        except Exception:
            pass

    async def uptime_loop(self):
        while self.running:
            await asyncio.sleep(15)
            await self.send_uptime_ping()

    # ─── Message handler ─────────────────────────────────────────

    async def handle_maze_init(self, data: dict):
        self.block_id = data.get("block_id")
        self.maze = data.get("maze")
        self.start = tuple(data.get("start"))
        self.goal = tuple(data.get("goal"))
        self.step_interval = data.get("step_interval", STEP_INTERVAL)
        self.deadline = data.get("deadline")
        self.current_pos = self.start
        self.round_active = True
        self.steps_taken = 0
        self.total_steps = 0
        print(f"{CYAN}Block #{self.block_id} — Mining with AI...{RESET}")
        await self.navigate_maze()

    async def message_loop(self):
        try:
            async for message in self.websocket:
                # ─── DEBUG: print every raw message ─────────────────
                print(f"{CYAN}[DEBUG] Raw message: {message}{RESET}")
                data = json.loads(message)
                msg_type = data.get("type")
                if msg_type == "pong":
                    continue
                elif msg_type == "maze_init":
                    await self.handle_maze_init(data)
                elif msg_type == "maze_move_ack":
                    if data.get("success"):
                        state = data.get("state")
                        if state:
                            self.current_pos = tuple(state.get("current"))
                        if state and state.get("finished"):
                            self.round_active = False
                            print(f"\n{GREEN}🏆 BLOCK SUBMITTED! 🏆{RESET}")
                    else:
                        print(f"{RED}✗ Move rejected: {data.get('message')}{RESET}")
                elif msg_type == "block_accepted":
                    reward = data.get('reward', 0)
                    print(f"{GREEN}✅ Block accepted! Reward: {reward} MCX{RESET}")
                elif msg_type == "error":
                    print(f"{RED}⚠️ Node error: {data.get('message')}{RESET}")
                else:
                    print(f"{DIM}[DEBUG] Unhandled message type: {msg_type} -> {data}{RESET}")
        except websockets.exceptions.ConnectionClosed:
            print(f"{YELLOW}⚠️ WebSocket closed, reconnecting...{RESET}")
            self.round_active = False
            self.block_id = -1
            raise  # re-raise to be caught by run loop

    # ─── Reconnection ────────────────────────────────────────────

    async def reconnect(self):
        delay = self.reconnect_delay
        while self.running:
            print(f"{CYAN}⏳ Reconnecting in {delay:.1f}s...{RESET}")
            await asyncio.sleep(delay)
            delay = min(delay * 1.5 + random.uniform(0, self.jitter), self.max_reconnect_delay)
            target_urls = []
            if self.node_url:
                target_urls = [self.node_url]
            else:
                target_urls = await self.discover_nodes()
                if not target_urls:
                    local_url = self.read_local_tunnel()
                    if local_url:
                        target_urls = [local_url]
            if not target_urls:
                continue

            for url in target_urls:
                if await self.connect(url):
                    if await self.register():
                        print(f"{GREEN}✅ Re-registered{RESET}")
                        self.round_active = False
                        self.block_id = -1
                        self.start_time = time.time()
                        self.uptime_seconds = 0
                        self.today_uptime = 0
                        return
                    else:
                        await self.websocket.close()
                        continue

    # ─── Main loop ──────────────────────────────────────────────

    async def run(self):
        print(BANNER)
        print(f"{WHITE}Starting AI PoMR Miner v27 (Terminal + Debug)...{RESET}\n")
        print(f"{CYAN}Hardware: {DEVICE}{RESET}")
        print(f"{CYAN}Training batch size: {TRAIN_BATCH_SIZE}{RESET}")
        print(f"{CYAN}Training epochs per maze: {TRAIN_EPOCHS_PER_MAZE}{RESET}\n")

        while self.running:
            target_urls = []
            if self.node_url:
                target_urls = [self.node_url]
            else:
                print(f"{CYAN}⏳ Discovering nodes via registry...{RESET}")
                target_urls = await self.discover_nodes()
                if not target_urls:
                    local_url = self.read_local_tunnel()
                    if local_url:
                        print(f"{CYAN}⏳ Using local tunnel URL{RESET}")
                        target_urls = [local_url]
                    else:
                        print(f"{YELLOW}⚠️ No nodes found, retrying in 10s...{RESET}")
                        await asyncio.sleep(10)
                        continue

            for url in target_urls:
                print(f"{CYAN}⏳ Attempting to connect to {url}{RESET}")
                if await self.connect(url):
                    if await self.is_connected():
                        if await self.register():
                            asyncio.create_task(self.uptime_loop())
                            try:
                                await self.message_loop()
                            except websockets.exceptions.ConnectionClosed:
                                print(f"{YELLOW}⚠️ Connection lost, reconnecting...{RESET}")
                                await self.reconnect()
                                break
                            except Exception as e:
                                print(f"{RED}✗ Unexpected error in message loop: {e}{RESET}")
                                break
                            break
                        else:
                            await self.websocket.close()
                            continue
                    else:
                        print(f"{YELLOW}⚠️ Connection lost before registration{RESET}")
                        continue
                else:
                    print(f"{YELLOW}⚠️ Connection failed{RESET}")
                    continue
            if not self.running:
                break
            print(f"{YELLOW}⚠️ All nodes failed, retrying in 10s...{RESET}")
            await asyncio.sleep(10)

    async def stop(self):
        self.running = False
        self.save_model()

# ─── Main entry point ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="MUNEX PoMR Miner AI v27")
    parser.add_argument("--node", help="Direct WebSocket URL (optional)")
    parser.add_argument("--wallet", help="Wallet address (optional)")
    parser.add_argument("--privkey", help="Private key hex (optional)")
    parser.add_argument("--miner-id", help="Custom miner ID (optional)")
    args = parser.parse_args()

    wallet = args.wallet
    privkey = args.privkey

    if not wallet or not privkey:
        loaded = load_wallet()
        if loaded:
            wallet, privkey = loaded
            print(f"{CYAN}Using saved wallet: {wallet}{RESET}")
        else:
            print("\n" + "="*50)
            print("Wallet setup")
            print("="*50)
            choice = input("Enter '1' to use an existing wallet, or press Enter to generate a new one: ").strip()
            if choice == '1':
                wallet = input("Wallet address (0x...): ").strip()
                privkey = input("Private key (hex): ").strip()
                if not wallet or not privkey:
                    print("Invalid input. Generating new wallet.")
                    wallet = privkey = None
            else:
                wallet = privkey = None

    miner = AIMiner(
        node_url=args.node or "",
        wallet=wallet or "",
        privkey=privkey or "",
        miner_id=args.miner_id or ""
    )
    try:
        await miner.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⏹️ Miner stopped{RESET}")
        await miner.stop()
        if miner.websocket:
            await miner.websocket.close()

if __name__ == "__main__":
    asyncio.run(main())