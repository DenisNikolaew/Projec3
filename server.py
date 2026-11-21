import uuid
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import SessionLocal, init_db, User, UserSession, Character, Location, Item, Inventory

app = FastAPI(title="Text RPG Server")
init_db()

WORLD_CHAT = ["[СИСТЕМА]: Сервер запущен!"]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AuthReq(BaseModel):
    username: str
    password: str = "1234"

class ActionReq(BaseModel):
    token: str
    action: str
    location_id: int = 1

class InteractReq(BaseModel):
    token: str
    recipient_char: str = ""
    item_name: str = ""
    chat_text: str = ""

def get_current_user(token: str, db: Session) -> User:
    session = db.query(UserSession).filter(UserSession.session_token == token).first()
    if not session or (session.expires_at and session.expires_at < datetime.utcnow()):
        raise HTTPException(status_code=401, detail="Сессия истекла или не найдена. Войдите заново.")
    
    session.expires_at = datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    return session.user

@app.post("/login")
def login(req: AuthReq, db: Session = Depends(get_db)):
    if not req.username.strip():
        raise HTTPException(status_code=400, detail="Имя не может быть пустым")

    user = db.query(User).filter(User.username == req.username).first()

    if not user:
        loc = db.query(Location).first()
        if not loc:
            loc = Location(location_name="Таверна")
            db.add(loc)
            db.commit()
            db.refresh(loc)

        char = Character(character_name=req.username, character_health=100, character_level=1)
        db.add(char)
        db.commit()
        db.refresh(char)

        user = User(
            username=req.username,
            userpassword=req.password,
            character_id=char.character_id,
            location_id=loc.location_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = str(uuid.uuid4())
    new_session = UserSession(
        session_token=token,
        user_id=user.user_id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )
    db.add(new_session)
    db.commit()

    return {"token": token, "username": user.username}

@app.get("/state/{token}")
def get_state(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    char = user.character

    now = datetime.utcnow()
    active_sessions = db.query(UserSession).filter(UserSession.expires_at >= now).all()
    online_names = list({s.user.username for s in active_sessions if s.user})

    leaders = db.query(Character).order_by(Character.character_level.desc()).limit(5).all()
    locations = db.query(Location).all()

    return {
        "player": {
            "username": char.character_name,
            "hp": char.character_health,
            "level": char.character_level,
            "location": user.location.location_name if user.location else "Таверна",
            "inventory": [
                {"name": inv.item.item_name, "count": inv.quantity}
                for inv in char.inventory_items if inv.item
            ]
        },
        "locations": [{"id": l.location_id, "name": l.location_name} for l in locations],
        "online_players": online_names,
        "leaderboard": [{"username": c.character_name, "score": f"Ур. {c.character_level}"} for c in leaders],
        "logs": WORLD_CHAT[-10:]
    }

@app.post("/action")
def do_action(req: ActionReq, db: Session = Depends(get_db)):
    user = get_current_user(req.token, db)
    char = user.character

    if req.action == "move":
        loc = db.query(Location).filter(Location.location_id == req.location_id).first()
        if not loc:
            raise HTTPException(status_code=404, detail="Локация не найдена")
        user.location_id = loc.location_id
        db.commit()
        return {"message": f"Вы перешли в локацию: {loc.location_name}"}

    elif req.action == "heal":
        char.character_health = min(100, char.character_health + 30)
        db.commit()
        return {"message": f"Вы отдохнули. Текущее здоровье: {char.character_health} HP."}

    elif req.action == "explore":
        if char.character_health <= 0:
            return {"message": "Вы без сознания! Сначала восстановите здоровье."}

        dmg = random.randint(5, 20)
        char.character_health = max(0, char.character_health - dmg)

        if char.character_health == 0:
            db.commit()
            return {"message": f"Монстр нанёс {dmg} урона. Вы повержены!"}

        msg = f"Победа! Потеряно {dmg} HP."
        if random.random() < 0.4:
            char.character_level += 1
            msg += f" Повышен уровень: {char.character_level}!"

        all_items = db.query(Item).all()
        if all_items and random.random() < 0.5:
            dropped = random.choice(all_items)
            inv_row = db.query(Inventory).filter(
                Inventory.character_id == char.character_id,
                Inventory.item_id == dropped.item_id
            ).first()
            if inv_row:
                inv_row.quantity += 1
            else:
                db.add(Inventory(character_id=char.character_id, item_id=dropped.item_id, quantity=1, slot_index=1))
            msg += f" Найден предмет: {dropped.item_name}!"

        db.commit()
        return {"message": msg}

@app.post("/interact")
def interact(req: InteractReq, db: Session = Depends(get_db)):
    user = get_current_user(req.token, db)
    char = user.character

    if req.recipient_char and req.item_name:
        target = db.query(Character).filter(Character.character_name == req.recipient_char).first()
        if not target:
            raise HTTPException(status_code=404, detail="Персонаж не найден")

        inv_item = (
            db.query(Inventory)
            .join(Item)
            .filter(Inventory.character_id == char.character_id, Item.item_name == req.item_name)
            .first()
        )
        if not inv_item or inv_item.quantity < 1:
            raise HTTPException(status_code=400, detail="У вас нет такого предмета")

        inv_item.quantity -= 1
        item_id = inv_item.item_id
        if inv_item.quantity == 0:
            db.delete(inv_item)

        target_inv = db.query(Inventory).filter(
            Inventory.character_id == target.character_id,
            Inventory.item_id == item_id
        ).first()
        if target_inv:
            target_inv.quantity += 1
        else:
            db.add(Inventory(character_id=target.character_id, item_id=item_id, quantity=1, slot_index=1))

        WORLD_CHAT.append(f"[ОБМЕН]: {char.character_name} передал {req.item_name} игроку {target.character_name}")
        db.commit()

    if req.chat_text.strip():
        WORLD_CHAT.append(f"[{char.character_name}]: {req.chat_text.strip()}")

    return {"status": "ok"}
