import cv2
import numpy as np
import mediapipe as mp
import random
import time

# --- Game settings ---
WIDTH, HEIGHT = 640, 480
CELL = 20
STEP_DELAY = 0.15          # seconds per snake move (lower = faster)
MIN_POINT_LEN = 40         # min finger length in px to count as a pointing direction

OPPOSITE = {'UP': 'DOWN', 'DOWN': 'UP', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'}

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils


# --- Game helpers ---
def random_food(snake):
    while True:
        pos = [random.randrange(0, WIDTH, CELL), random.randrange(0, HEIGHT, CELL)]
        if pos not in snake:
            return pos


def new_game():
    snake = [[WIDTH // 2, HEIGHT // 2]]
    return snake, 'UP', 0, random_food(snake)


# --- Gesture helpers ---
def finger_states(lm):
    """Return [thumb, index, middle, ring, pinky] -> True if extended.
    A finger is extended if its tip is farther from the wrist than its PIP joint
    (works at any hand rotation)."""
    wrist = np.array([lm[0].x, lm[0].y])

    def dist(i):
        return np.linalg.norm(np.array([lm[i].x, lm[i].y]) - wrist)

    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]
    return [dist(t) > dist(p) for t, p in zip(tips, pips)]


def read_gesture(lm, current):
    """Return (gesture_name, new_direction)."""
    thumb, index, middle, ring, pinky = finger_states(lm)
    others_curled = not (middle or ring or pinky)

    if not any([index, middle, ring, pinky]):
        return "FIST (paused)", None

    if index and others_curled:                      # pointing gesture
        # direction from index knuckle (5) to index tip (8), in pixels
        dx = (lm[8].x - lm[5].x) * WIDTH
        dy = (lm[8].y - lm[5].y) * HEIGHT
        if max(abs(dx), abs(dy)) < MIN_POINT_LEN:
            return "POINT", current
        if abs(dx) > abs(dy):
            new = 'RIGHT' if dx > 0 else 'LEFT'
        else:
            new = 'DOWN' if dy > 0 else 'UP'
        if new == OPPOSITE[current]:                 # block 180-degree turns
            new = current
        return f"POINT {new}", new

    return "OPEN HAND (go)", current


# --- Setup ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise SystemExit("Cannot open camera. On macOS, allow camera access for "
                     "your terminal/IDE in System Settings > Privacy & Security > Camera.")

snake, direction, score, food = new_game()
paused = True              # starts paused until a hand is shown
last_step = time.time()

with mp_hands.Hands(max_num_hands=1,
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.6) as hands:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (WIDTH, HEIGHT))

        # --- Hand gesture detection ---
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        label = "NO HAND (paused)"
        paused = True

        if result.multi_hand_landmarks:
            hand_lm = result.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
            label, new_dir = read_gesture(hand_lm.landmark, direction)
            if new_dir is None:
                paused = True                         # fist
            else:
                direction = new_dir
                paused = False

        # --- Move snake on a fixed timer ---
        if not paused and time.time() - last_step >= STEP_DELAY:
            last_step = time.time()
            hx, hy = snake[0]
            if direction == 'UP':      hy -= CELL
            elif direction == 'DOWN':  hy += CELL
            elif direction == 'LEFT':  hx -= CELL
            elif direction == 'RIGHT': hx += CELL
            head = [hx % WIDTH, hy % HEIGHT]          # wrap around edges

            if head in snake[:-1]:                    # hit itself
                cv2.putText(frame, "GAME OVER!", (WIDTH // 6, HEIGHT // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                cv2.imshow("Gesture Snake", frame)
                cv2.waitKey(2000)
                snake, direction, score, food = new_game()
                continue

            snake.insert(0, head)
            if head == food:
                score += 1
                food = random_food(snake)
            else:
                snake.pop()

        # --- Draw ---
        cv2.rectangle(frame, (food[0], food[1]),
                      (food[0] + CELL, food[1] + CELL), (0, 0, 255), -1)
        for sx, sy in snake:
            cv2.rectangle(frame, (sx, sy), (sx + CELL, sy + CELL), (255, 0, 0), -1)
        cv2.putText(frame, f'Score: {score}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(frame, f'Gesture: {label}', (10, HEIGHT - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow("Gesture Snake", frame)
        if cv2.waitKey(1) & 0xFF == 27:               # ESC to quit
            break

cap.release()
cv2.destroyAllWindows()