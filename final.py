import streamlit as st
import sqlite3
import bcrypt
import os
import uuid
import datetime

# Set page configuration
st.set_page_config(page_title="Air Gesture Games Hub", layout="wide")

# Database setup
def update_db_schema():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists or other non-critical error
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            login_timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Initialize admin user
    admin_email = "vvalliappan2004@gmail.com"
    admin_password = "csc123"
    admin_username = "admin"
    hashed = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
    try:
        c.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  (admin_username, admin_email, hashed, True))
        conn.commit()
    except sqlite3.IntegrityError:
        # Admin user already exists, update password if needed
        c.execute("UPDATE users SET password = ?, is_admin = ? WHERE email = ?",
                  (hashed, True, admin_email))
        conn.commit()
    conn.close()

# User authentication functions
def signup(username, email, password, is_admin=False):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        c.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  (username, email, hashed, is_admin))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login(email, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    try:
        c.execute("SELECT id, password, is_admin FROM users WHERE email = ?", (email,))
        result = c.fetchone()
        if result and bcrypt.checkpw(password.encode('utf-8'), result[1]):
            user_id, _, is_admin = result
            timestamp = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO sessions (user_id, login_timestamp) VALUES (?, ?)",
                      (user_id, timestamp))
            conn.commit()
            conn.close()
            return user_id, is_admin
    except sqlite3.OperationalError as e:
        st.error(f"Database error: {e}")
    conn.close()
    return None, None

def save_score(user_id, game_type, score):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    c.execute("INSERT INTO scores (user_id, game_type, score, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, game_type, score, timestamp))
    conn.commit()
    conn.close()

def get_user_scores(user_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT game_type, score, timestamp FROM scores WHERE user_id = ? ORDER BY timestamp DESC",
              (user_id,))
    scores = c.fetchall()
    conn.close()
    return scores

def get_leaderboard(game_type):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        SELECT u.username, MAX(s.score) as high_score
        FROM scores s
        JOIN users u ON s.user_id = u.id
        WHERE s.game_type = ?
        GROUP BY u.id, u.username
        ORDER BY high_score DESC
        LIMIT 10
    """, (game_type,))
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

def get_active_sessions():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        SELECT u.username, u.email, s.login_timestamp
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.login_timestamp DESC
    """)
    sessions = c.fetchall()
    conn.close()
    return sessions

# HTML generation functions for games
def generate_air_touch_game_html():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Air Touch Sensitivity Game</title>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js"></script>
        <style>
            body {
                margin: 0;
                overflow: hidden;
                background: #1a1a1a;
                color: #fff;
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                user-select: none;
            }
            canvas {
                border: 2px solid #444;
                background: #000;
            }
            #ui {
                position: absolute;
                top: 10px;
                left: 10px;
                text-align: left;
            }
            #score, #time, #level {
                font-size: 24px;
                margin: 5px 0;
            }
            #start-screen, #game-over-screen {
                position: absolute;
                background: rgba(0, 0, 0, 0.8);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                display: none;
            }
            button {
                padding: 10px 20px;
                font-size: 18px;
                background: #4caf50;
                border: none;
                color: white;
                cursor: pointer;
                border-radius: 5px;
            }
            button:hover {
                background: #45a049;
            }
            #video {
                display: none;
            }
        </style>
    </head>
    <body>
        <div id="ui">
            <div id="score">Score: 0</div>
            <div id="time">Time: 30</div>
            <div id="level">Level: 1</div>
        </div>
        <canvas id="gameCanvas"></canvas>
        <video id="video" autoplay></video>
        <div id="start-screen">
            <h1>Air Touch Sensitivity</h1>
            <p>Use hand gestures to hit the targets! Point your index finger to control the cursor.</p>
            <button id="start-button">Start Game</button>
        </div>
        <div id="game-over-screen">
            <h1>Game Over</h1>
            <p id="final-score">Score: 0</p>
            <p>Enter this score below to save it!</p>
            <button id="restart-button">Play Again</button>
        </div>
        <script>
            const canvas = document.getElementById('gameCanvas');
            const ctx = canvas.getContext('2d');
            const video = document.getElementById('video');
            const startScreen = document.getElementById('start-screen');
            const gameOverScreen = document.getElementById('game-over-screen');
            const startButton = document.getElementById('start-button');
            const restartButton = document.getElementById('restart-button');
            const scoreDisplay = document.getElementById('score');
            const timeDisplay = document.getElementById('time');
            const levelDisplay = document.getElementById('level');
            const finalScoreDisplay = document.getElementById('final-score');

            let width, height, targets = [], score = 0, timeLeft = 30, level = 1;
            let gameState = 'start', lastFrameTime = performance.now();
            let cursorPos = { x: -10, y: -10 }, handDetected = false;
            const maxTargets = 10, baseTargetRadius = 20;

            const hands = new Hands({locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`;
            }});
            hands.setOptions({
                maxNumHands: 1,
                modelComplexity: 1,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5
            });
            hands.onResults(onResults);

            const camera = new Camera(video, {
                onFrame: async () => {
                    await hands.send({image: video});
                },
                width: 640,
                height: 480
            });

            function onResults(results) {
                if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                    const landmarks = results.multiHandLandmarks[0];
                    const indexTip = landmarks[8];
                    cursorPos.x = (1 - indexTip.x) * width;
                    cursorPos.y = indexTip.y * height;
                    handDetected = true;
                } else {
                    handDetected = false;
                }
            }

            function resizeCanvas() {
                width = window.innerWidth * 0.9;
                height = window.innerHeight * 0.7;
                canvas.width = width;
                canvas.height = height;
                canvas.style.width = `${width}px`;
                canvas.style.height = `${height}px`;
            }

            function createTarget() {
                const radius = baseTargetRadius / Math.sqrt(level);
                const speed = 2 + level * 0.5;
                return {
                    x: Math.random() * (width - 2 * radius) + radius,
                    y: Math.random() * (height - 2 * radius) + radius,
                    vx: (Math.random() - 0.5) * speed,
                    vy: (Math.random() - 0.5) * speed,
                    radius: radius,
                    color: `hsl(${Math.random() * 360}, 70%, 50%)`
                };
            }

            function updateTargets(deltaTime) {
                targets.forEach(t => {
                    t.x += t.vx * deltaTime * 60;
                    t.y += t.vy * deltaTime * 60;
                    if (t.x < t.radius || t.x > width - t.radius) t.vx *= -1;
                    if (t.y < t.radius || t.y > height - t.radius) t.vy *= -1;
                });
            }

            function checkHits() {
                targets = targets.filter(t => {
                    const dx = t.x - cursorPos.x;
                    const dy = t.y - cursorPos.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    if (distance < t.radius) {
                        score += Math.floor(10 * level);
                        scoreDisplay.textContent = `Score: ${score}`;
                        return false;
                    }
                    return true;
                });
            }

            function spawnTargets() {
                if (targets.length < maxTargets && Math.random() < 0.02 * level) {
                    targets.push(createTarget());
                }
            }

            function draw() {
                ctx.clearRect(0, 0, width, height);
                targets.forEach(t => {
                    ctx.beginPath();
                    ctx.arc(t.x, t.y, t.radius, 0, Math.PI * 2);
                    ctx.fillStyle = t.color;
                    ctx.fill();
                });
                if (gameState === 'playing' && handDetected) {
                    ctx.beginPath();
                    ctx.arc(cursorPos.x, cursorPos.y, 5, 0, Math.PI * 2);
                    ctx.fillStyle = 'white';
                    ctx.fill();
                }
            }

            function updateTimer(deltaTime) {
                timeLeft -= deltaTime;
                timeDisplay.textContent = `Time: ${Math.max(0, Math.floor(timeLeft))}`;
                if (timeLeft <= 0) {
                    gameState = 'gameOver';
                    gameOverScreen.style.display = 'block';
                    finalScoreDisplay.textContent = `Score: ${score}`;
                    camera.stop();
                }
            }

            function updateLevel() {
                level = Math.floor(score / 100) + 1;
                levelDisplay.textContent = `Level: ${level}`;
            }

            function gameLoop(currentTime) {
                if (gameState !== 'playing') return;
                const deltaTime = (currentTime - lastFrameTime) / 1000;
                lastFrameTime = currentTime;
                updateTargets(deltaTime);
                checkHits();
                spawnTargets();
                updateTimer(deltaTime);
                updateLevel();
                draw();
                requestAnimationFrame(gameLoop);
            }

            function startGame() {
                gameState = 'playing';
                startScreen.style.display = 'none';
                gameOverScreen.style.display = 'none';
                score = 0;
                timeLeft = 30;
                level = 1;
                targets = [];
                cursorPos = { x: -10, y: -10 };
                handDetected = false;
                scoreDisplay.textContent = `Score: ${score}`;
                timeDisplay.textContent = `Time: ${timeLeft}`;
                levelDisplay.textContent = `Level: ${level}`;
                lastFrameTime = performance.now();
                camera.start();
                requestAnimationFrame(gameLoop);
            }

            function resetGame() {
                startGame();
            }

            startButton.addEventListener('click', startGame);
            restartButton.addEventListener('click', resetGame);
            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();
            startScreen.style.display = 'block';
        </script>
    </body>
    </html>
    """
    return html_content

def generate_tic_tac_toe_html():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hand Gesture Tic-Tac-Toe</title>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js"></script>
        <style>
            body {
                margin: 0;
                overflow: hidden;
                background: #1a1a1a;
                color: #fff;
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                user-select: none;
            }
            canvas {
                border: 2px solid #444;
                background: #fff;
            }
            #ui {
                position: absolute;
                top: 10px;
                left: 10px;
                text-align: left;
            }
            #status {
                font-size: 24px;
                margin: 5px 0;
            }
            #start-screen, #game-over-screen {
                position: absolute;
                background: rgba(0, 0, 0, 0.8);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                display: none;
            }
            button {
                padding: 10px 20px;
                font-size: 18px;
                background: #4caf50;
                border: none;
                color: white;
                cursor: pointer;
                border-radius: 5px;
            }
            button:hover {
                background: #45a049;
            }
            #video {
                display: none;
            }
        </style>
    </head>
    <body>
        <div id="ui">
            <div id="status">Your turn (X)</div>
        </div>
        <canvas id="gameCanvas"></canvas>
        <video id="video" autoplay></video>
        <div id="start-screen">
            <h1>Hand Gesture Tic-Tac-Toe</h1>
            <p>Point your index finger at a cell and hold for 0.5 seconds to place an X. Can you beat the unbeatable AI?</p>
            <button id="start-button">Start Game</button>
        </div>
        <div id="game-over-screen">
            <h1>Game Over</h1>
            <p id="result">Result</p>
            <p id="final-score">Score: 0</p>
            <p>Enter this score below to save it!</p>
            <button id="restart-button">Play Again</button>
        </div>
        <script>
            const canvas = document.getElementById('gameCanvas');
            const ctx = canvas.getContext('2d');
            const video = document.getElementById('video');
            const startScreen = document.getElementById('start-screen');
            const gameOverScreen = document.getElementById('game-over-screen');
            const startButton = document.getElementById('start-button');
            const restartButton = document.getElementById('restart-button');
            const statusDisplay = document.getElementById('status');
            const resultDisplay = document.getElementById('result');
            const finalScoreDisplay = document.getElementById('final-score');

            let width, height, board = Array(9).fill(null), currentPlayer = 'X';
            let gameState = 'start', lastFrameTime = performance.now();
            let cursorPos = { x: -10, y: -10 }, hoverCell = null, hoverTime = 0;
            let handDetected = false;
            const gridSize = 3, cellSize = 100, holdTime = 0.5;

            const hands = new Hands({locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`;
            }});
            hands.setOptions({
                maxNumHands: 1,
                modelComplexity: 1,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5
            });
            hands.onResults(onResults);

            const camera = new Camera(video, {
                onFrame: async () => {
                    await hands.send({image: video});
                },
                width: 640,
                height: 480
            });

            function onResults(results) {
                if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                    const landmarks = results.multiHandLandmarks[0];
                    const indexTip = landmarks[8];
                    cursorPos.x = (1 - indexTip.x) * width;
                    cursorPos.y = indexTip.y * height;
                    handDetected = true;
                } else {
                    handDetected = false;
                }
            }

            function resizeCanvas() {
                width = gridSize * cellSize;
                height = gridSize * cellSize;
                canvas.width = width;
                canvas.height = height;
                canvas.style.width = `${width}px`;
                canvas.style.height = `${height}px`;
            }

            function getCellIndex(x, y) {
                const row = Math.floor(y / cellSize);
                const col = Math.floor(x / cellSize);
                if (row >= 0 && row < gridSize && col >= 0 && col < gridSize) {
                    return row * gridSize + col;
                }
                return null;
            }

            function checkWin(player, tempBoard) {
                const winConditions = [
                    [0, 1, 2], [3, 4, 5], [6, 7, 8],
                    [0, 3, 6], [1, 4, 7], [2, 5, 8],
                    [0, 4, 8], [2, 4, 6]
                ];
                return winConditions.some(condition =>
                    condition.every(index => tempBoard[index] === player)
                );
            }

            function checkDraw(tempBoard) {
                return tempBoard.every(cell => cell !== null);
            }

            function minimax(tempBoard, isMaximizing) {
                if (checkWin('O', tempBoard)) return { score: 10 };
                if (checkWin('X', tempBoard)) return { score: -10 };
                if (checkDraw(tempBoard)) return { score: 0 };

                if (isMaximizing) {
                    let bestScore = -Infinity;
                    let bestMove = null;
                    for (let i = 0; i < 9; i++) {
                        if (tempBoard[i] === null) {
                            tempBoard[i] = 'O';
                            const result = minimax(tempBoard, false);
                            tempBoard[i] = null;
                            if (result.score > bestScore) {
                                bestScore = result.score;
                                bestMove = i;
                            }
                        }
                    }
                    return { score: bestScore, move: bestMove };
                } else {
                    let bestScore = Infinity;
                    let bestMove = null;
                    for (let i = 0; i < 9; i++) {
                        if (tempBoard[i] === null) {
                            tempBoard[i] = 'X';
                            const result = minimax(tempBoard, true);
                            tempBoard[i] = null;
                            if (result.score < bestScore) {
                                bestScore = result.score;
                                bestMove = i;
                            }
                        }
                    }
                    return { score: bestScore, move: bestMove };
                }
            }

            function aiMove() {
                const result = minimax([...board], true);
                if (result.move !== null) {
                    board[result.move] = 'O';
                    if (checkWin('O', board)) {
                        gameState = 'gameOver';
                        resultDisplay.textContent = 'AI (O) Wins!';
                        finalScoreDisplay.textContent = `Score: 0`;
                        gameOverScreen.style.display = 'block';
                        camera.stop();
                    } else if (checkDraw(board)) {
                        gameState = 'gameOver';
                        resultDisplay.textContent = 'Draw!';
                        finalScoreDisplay.textContent = `Score: 50`;
                        gameOverScreen.style.display = 'block';
                        camera.stop();
                    } else {
                        currentPlayer = 'X';
                        statusDisplay.textContent = 'Your turn (X)';
                    }
                }
            }

            function handlePlayerMove(deltaTime) {
                if (!handDetected) return;
                const cellIndex = getCellIndex(cursorPos.x, cursorPos.y);
                if (cellIndex !== null && board[cellIndex] === null) {
                    if (cellIndex === hoverCell) {
                        hoverTime += deltaTime;
                        if (hoverTime >= holdTime) {
                            board[cellIndex] = 'X';
                            hoverCell = null;
                            hoverTime = 0;
                            if (checkWin('X', board)) {
                                gameState = 'gameOver';
                                resultDisplay.textContent = 'You (X) Win!';
                                finalScoreDisplay.textContent = `Score: 100`;
                                gameOverScreen.style.display = 'block';
                                camera.stop();
                            } else if (checkDraw(board)) {
                                gameState = 'gameOver';
                                resultDisplay.textContent = 'Draw!';
                                finalScoreDisplay.textContent = `Score: 50`;
                                gameOverScreen.style.display = 'block';
                                camera.stop();
                            } else {
                                currentPlayer = 'O';
                                statusDisplay.textContent = 'AI turn (O)';
                                setTimeout(aiMove, 500);
                            }
                        }
                    } else {
                        hoverCell = cellIndex;
                        hoverTime = 0;
                    }
                } else {
                    hoverCell = null;
                    hoverTime = 0;
                }
            }

            function draw() {
                ctx.clearRect(0, 0, width, height);
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 5;
                for (let i = 1; i < gridSize; i++) {
                    ctx.beginPath();
                    ctx.moveTo(i * cellSize, 0);
                    ctx.lineTo(i * cellSize, height);
                    ctx.stroke();
                    ctx.beginPath();
                    ctx.moveTo(0, i * cellSize);
                    ctx.lineTo(width, i * cellSize);
                    ctx.stroke();
                }
                ctx.font = '60px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                board.forEach((cell, index) => {
                    if (cell) {
                        const row = Math.floor(index / gridSize);
                        const col = index % gridSize;
                        ctx.fillStyle = cell === 'X' ? '#ff0000' : '#0000ff';
                        ctx.fillText(cell, col * cellSize + cellSize / 2, row * cellSize + cellSize / 2);
                    }
                });
                if (hoverCell !== null && gameState === 'playing' && currentPlayer === 'X' && handDetected) {
                    const row = Math.floor(hoverCell / gridSize);
                    const col = hoverCell % gridSize;
                    ctx.fillStyle = 'rgba(0, 255, 0, 0.2)';
                    ctx.fillRect(col * cellSize, row * cellSize, cellSize, cellSize);
                }
                if (gameState === 'playing' && handDetected) {
                    ctx.beginPath();
                    ctx.arc(cursorPos.x, cursorPos.y, 5, 0, Math.PI * 2);
                    ctx.fillStyle = 'black';
                    ctx.fill();
                }
            }

            function gameLoop(currentTime) {
                if (gameState !== 'playing') return;
                const deltaTime = (currentTime - lastFrameTime) / 1000;
                lastFrameTime = currentTime;
                if (currentPlayer === 'X') {
                    handlePlayerMove(deltaTime);
                }
                draw();
                requestAnimationFrame(gameLoop);
            }

            function startGame() {
                gameState = 'playing';
                startScreen.style.display = 'none';
                gameOverScreen.style.display = 'none';
                board = Array(9).fill(null);
                currentPlayer = 'X';
                cursorPos = { x: -10, y: -10 };
                hoverCell = null;
                hoverTime = 0;
                handDetected = false;
                statusDisplay.textContent = 'Your turn (X)';
                lastFrameTime = performance.now();
                camera.start();
                requestAnimationFrame(gameLoop);
            }

            function resetGame() {
                startGame();
            }

            startButton.addEventListener('click', startGame);
            restartButton.addEventListener('click', resetGame);
            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();
            startScreen.style.display = 'block';
        </script>
    </body>
    </html>
    """
    return html_content

# Streamlit app
def main():
    update_db_schema()
    init_db()

    if 'user_logged_in' not in st.session_state:
        st.session_state.user_logged_in = False
        st.session_state.user_id = None
        st.session_state.admin_logged_in = False
        st.session_state.admin_id = None
        st.session_state.selected_game = None
        st.session_state.page = 'login'
        st.session_state.score_saved = False

    st.title("Air Gesture Games Hub")
    tab1, tab2, tab3 = st.tabs(["User Login", "User Signup", "Admin Login"])

    # User Login
    with tab1:
        st.subheader("User Login")
        user_email = st.text_input("Email", key="user_login_email")
        user_password = st.text_input("Password", type="password", key="user_login_password")
        if st.button("Login", key="user_login_button"):
            user_id, is_admin = login(user_email, user_password)
            if user_id and not is_admin:
                st.session_state.user_logged_in = True
                st.session_state.user_id = user_id
                st.session_state.admin_logged_in = False
                st.session_state.admin_id = None
                st.session_state.selected_game = None
                st.session_state.page = 'dashboard'
                st.session_state.score_saved = False
                st.success("Logged in successfully!")
                st.rerun()
            elif is_admin:
                st.error("Please use the Admin Login tab for admin accounts.")
            else:
                st.error("Invalid email or password.")

    # User Signup
    with tab2:
        st.subheader("User Signup")
        username = st.text_input("Username", key="signup_username")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        admin_code = st.text_input("Admin Code (optional)", type="password", key="signup_admin_code")
        if st.button("Signup", key="signup_button"):
            is_admin = admin_code == "secret_admin_123"  # Replace with a secure code
            if signup(username, email, password, is_admin):
                st.success("Signed up successfully! Please login.")
            else:
                st.error("Email already exists.")

    # Admin Login
    with tab3:
        st.subheader("Admin Login")
        admin_email = st.text_input("Email", key="admin_login_email")
        admin_password = st.text_input("Password", type="password", key="admin_login_password")
        if st.button("Login", key="admin_login_button"):
            admin_id, is_admin = login(admin_email, admin_password)
            if admin_id and is_admin:
                st.session_state.admin_logged_in = True
                st.session_state.admin_id = admin_id
                st.session_state.user_logged_in = False
                st.session_state.user_id = None
                st.session_state.selected_game = None
                st.session_state.page = 'admin'
                st.session_state.score_saved = False
                st.success("Admin logged in successfully!")
                st.rerun()
            elif not is_admin and admin_id:
                st.error("Please use the User Login tab for non-admin accounts.")
            else:
                st.error("Invalid email or password.")

    # User Interface
    if st.session_state.user_logged_in:
        st.sidebar.title("User Navigation")
        page = st.sidebar.radio("Go to", ["Dashboard", "Profile", "Leaderboard"], key="user_page_selector")

        if page == "Dashboard":
            st.session_state.page = 'dashboard'
            st.write("Select a game to play using hand gestures. Ensure your webcam is enabled.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Pop the balls"):
                    st.session_state.selected_game = "air_touch"
                    st.session_state.score_saved = False
            with col2:
                if st.button("Hand Gesture Tic-Tac-Toe"):
                    st.session_state.selected_game = "tic_tac_toe"
                    st.session_state.score_saved = False

            if st.session_state.selected_game == "air_touch":
                st.subheader("Pop the balls")
                html_content = generate_air_touch_game_html()
                st.components.v1.html(html_content, height=600, scrolling=True)
                if not st.session_state.score_saved:
                    with st.form(key="air_touch_score_form"):
                        score = st.number_input("Enter your score (from the game-over screen):", min_value=0, step=1)
                        submit = st.form_submit_button("Submit Score")
                        if submit:
                            if score >= 0:
                                save_score(st.session_state.user_id, "air_touch", score)
                                st.session_state.score_saved = True
                                st.success("Score saved successfully!")
                            else:
                                st.error("Score must be non-negative.")
                else:
                    st.info("Score already submitted for this game session.")

            elif st.session_state.selected_game == "tic_tac_toe":
                st.subheader("Hand Gesture Tic-Tac-Toe")
                html_content = generate_tic_tac_toe_html()
                st.components.v1.html(html_content, height=600, scrolling=True)
                if not st.session_state.score_saved:
                    with st.form(key="tic_tac_toe_score_form"):
                        score = st.selectbox("Select your score (from the game-over screen):", [0, 50, 100])
                        submit = st.form_submit_button("Submit Score")
                        if submit:
                            if score in [0, 50, 100]:
                                save_score(st.session_state.user_id, "tic_tac_toe", score)
                                st.session_state.score_saved = True
                                st.success("Score saved successfully!")
                            else:
                                st.error("Invalid score. Choose 0, 50, or 100.")
                else:
                    st.info("Score already submitted for this game session.")

        elif page == "Profile":
            st.session_state.page = 'profile'
            st.subheader("Your Profile")
            scores = get_user_scores(st.session_state.user_id)
            if scores:
                st.write("Your Recent Scores:")
                for game_type, score, timestamp in scores:
                    game_name = "Pop the balls" if game_type == "air_touch" else "Tic-Tac-Toe"
                    st.write(f"{game_name}: {score} (Played on {timestamp})")
            else:
                st.write("No scores yet. Play a game to see your scores here!")

        elif page == "Leaderboard":
            st.session_state.page = 'leaderboard'
            st.subheader("Leaderboard")
            tab1, tab2 = st.tabs(["Pop the balls", "Tic-Tac-Toe"])
            with tab1:
                st.write("Top 10 High Scores for Air Touch Sensitivity")
                leaderboard = get_leaderboard("air_touch")
                if leaderboard:
                    for username, high_score in leaderboard:
                        st.write(f"{username}: {high_score}")
                else:
                    st.write("No scores yet.")
            with tab2:
                st.write("Top 10 High Scores for Tic-Tac-Toe")
                leaderboard = get_leaderboard("tic_tac_toe")
                if leaderboard:
                    for username, high_score in leaderboard:
                        st.write(f"{username}: {high_score}")
                else:
                    st.write("No scores yet.")

        if st.sidebar.button("Logout", key="user_logout"):
            st.session_state.user_logged_in = False
            st.session_state.user_id = None
            st.session_state.admin_logged_in = False
            st.session_state.admin_id = None
            st.session_state.selected_game = None
            st.session_state.page = 'login'
            st.session_state.score_saved = False
            st.success("Logged out successfully!")
            st.rerun()

    # Admin Interface
    elif st.session_state.admin_logged_in:
        st.sidebar.title("Admin Navigation")
        page = st.sidebar.radio("Go to", ["Admin Dashboard"], key="admin_page_selector")

        if page == "Admin Dashboard":
            st.session_state.page = 'admin'
            st.subheader("Admin Dashboard - Active User Sessions")
            sessions = get_active_sessions()
            if sessions:
                st.write("Currently logged-in users:")
                for username, email, login_timestamp in sessions:
                    st.write(f"Username: {username}, Email: {email}, Logged in at: {login_timestamp}")
            else:
                st.write("No active user sessions.")

        if st.sidebar.button("Logout", key="admin_logout"):
            st.session_state.admin_logged_in = False
            st.session_state.admin_id = None
            st.session_state.user_logged_in = False
            st.session_state.user_id = None
            st.session_state.selected_game = None
            st.session_state.page = 'login'
            st.session_state.score_saved = False
            st.success("Logged out successfully!")
            st.rerun()

if __name__ == "__main__":
    main()